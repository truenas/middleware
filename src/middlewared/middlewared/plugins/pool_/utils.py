import dataclasses
import enum
import itertools
import json
import os
from pathlib import Path
import re
import typing
from typing import TypedDict

from truenas_pydmi.models import TRUENAS_UNKNOWN

from middlewared.plugins.zfs_.utils import TNUserProp
from middlewared.service_exception import CallError
from middlewared.utils.filesystem.directory import directory_is_empty
from middlewared.utils.size import MB

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware

DATASET_DATABASE_MODEL_NAME = 'storage.encrypteddataset'
RE_DRAID_DATA_DISKS = re.compile(r':\d*d')
RE_DRAID_SPARE_DISKS = re.compile(r':\d*s')
RE_DRAID_NAME = re.compile(r'draid\d:\d+d:\d+c:\d+s-\d+')
ZFS_CHECKSUM_CHOICES = ['ON', 'OFF', 'FLETCHER2', 'FLETCHER4', 'SHA256', 'SHA512', 'SKEIN', 'EDONR', 'BLAKE3']
ZFS_COMPRESSION_ALGORITHM_CHOICES = [
    'ON', 'OFF', 'LZ4', 'GZIP', 'GZIP-1', 'GZIP-9', 'ZSTD', 'ZSTD-FAST', 'ZLE', 'LZJB',
] + [f'ZSTD-{i}' for i in range(1, 20)] + [
    f'ZSTD-FAST-{i}' for i in itertools.chain(range(1, 11), range(20, 110, 10), range(500, 1500, 500))
]
ZFS_ENCRYPTION_ALGORITHM_CHOICES = [
    'AES-128-CCM', 'AES-192-CCM', 'AES-256-CCM', 'AES-128-GCM', 'AES-192-GCM', 'AES-256-GCM'
]
ZFS_VOLUME_BLOCK_SIZE_CHOICES = {
    '512': 512,
    '512B': 512,
    '1K': 1024,
    '2K': 2048,
    '4K': 4096,
    '8K': 8192,
    '16K': 16384,
    '32K': 32768,
    '64K': 65536,
    '128K': 131072,
}
ZPOOL_CACHE_FILE = '/data/zfs/zpool.cache'
ZPOOL_KILLCACHE = '/data/zfs/killcache'


class CreateImplArgs(typing.TypedDict, total=False):
    name: str
    """The name of the resource being created."""
    ztype: typing.Literal["FILESYSTEM", "VOLUME"]
    """The type of the resource to be created."""
    zprops: dict[str, str]
    """ZFS data properties to be applied during creation."""
    uprops: dict[str, str] | None
    """ZFS user properties to be applied during creation."""
    encrypt: dict | None
    """Encryption related properties to be applied during creation."""
    create_ancestors: bool
    """Create ancestors for the zfs resource being created."""


@dataclasses.dataclass(slots=True, kw_only=True)
class CreateImplArgsDataclass:
    name: str
    """The name of the resource being created."""
    ztype: typing.Literal["FILESYSTEM", "VOLUME"]
    """The type of the resource to be created."""
    zprops: dict[str, str] = dataclasses.field(default_factory=dict)
    """ZFS data properties to be applied during creation."""
    uprops: dict[str, str] | None = None
    """ZFS user properties to be applied during creation."""
    encrypt: dict | None = None
    """Encryption related properties to be applied during creation."""
    create_ancestors: bool = False
    """Create ancestors for the zfs resource being created."""


class UpdateImplArgs(TypedDict, total=False):
    name: str
    """The name of the resource being created."""
    zprops: dict[str, str]
    """ZFS data properties to be applied during creation."""
    uprops: dict[str, str]
    """ZFS user properties to be applied during creation."""
    iprops: set
    """ZFS properties to be inherited from parent."""


@dataclasses.dataclass(slots=True, kw_only=True)
class UpdateImplArgsDataclass:
    name: str
    """The name of the resource being created."""
    zprops: dict[str, str] = dataclasses.field(default_factory=dict)
    """ZFS data properties to be applied during creation."""
    uprops: dict[str, str] = dataclasses.field(default_factory=dict)
    """ZFS user properties to be applied during creation."""
    iprops: set = dataclasses.field(default_factory=set)
    """ZFS properties to be inherited from parent."""


async def validate_dedup_license(middleware, verrors, schema, deduplication):
    """Reject enabling ZFS deduplication on systems that are not entitled to it.

    Licensed systems must carry the DEDUP feature flag; unlicensed TrueNAS hardware
    (iX-branded, excluding minis) is blocked; Community Edition and minis may use
    dedup freely. Only ON/VERIFY are gated.
    """
    if deduplication not in ('ON', 'VERIFY'):
        return

    if await middleware.call('system.license') is not None:
        # Any licensed system must carry the explicit DEDUP feature flag.
        if not await middleware.call('system.feature_enabled', 'DEDUP'):
            verrors.add(
                f'{schema}.deduplication',
                "This system's license does not include the ZFS deduplication feature."
            )
    else:
        # Unlicensed: Community Edition (incl. minis) may use dedup; TrueNAS hardware may not.
        chassis = await middleware.call('truenas.get_chassis_hardware')
        if chassis != TRUENAS_UNKNOWN and 'MINI' not in chassis:
            verrors.add(
                f'{schema}.deduplication',
                'This system is not licensed to use ZFS deduplication.'
            )


async def pool_has_special_vdev(middleware: 'Middleware', pool_name: str) -> bool:
    """Whether the pool has a SPECIAL allocation class vdev. Returns False when the
    pool cannot be inspected."""
    try:
        pools = await middleware.call(
            'zpool.query_impl',
            {'pool_names': [pool_name], 'properties': ['class_special_size']},
        )
        if not pools:
            return False
        special_size = ((pools[0].get('properties') or {}).get('class_special_size') or {}).get('value')
    except Exception:
        middleware.logger.debug('%s: failed to query pool SPECIAL vdev size', pool_name, exc_info=True)
        return False
    return isinstance(special_size, int) and special_size > 0


async def _dedup_inheriting_performance_descendants(middleware, dataset_name):
    """Names of FILESYSTEM descendants of ``dataset_name`` whose data placement is on
    the SPECIAL vdev (effective ``special_small_blocks`` > 0) and whose effective
    deduplication value would change with a deduplication value set on ``dataset_name``.
    Returns an empty list when the descendants cannot be inspected."""
    try:
        results = await middleware.call(
            'pool.dataset.query',
            [('id', '=', dataset_name)],
            {'extra': {'properties': ['dedup', 'special_small_blocks'], 'retrieve_user_props': False}},
        )
    except Exception:
        middleware.logger.debug('%s: failed to query descendant datasets', dataset_name, exc_info=True)
        return []
    if not results:
        return []

    affected = []
    stack = list(results[0].get('children') or [])
    while stack:
        ds = stack.pop()
        stack.extend(ds.get('children') or [])
        if ds.get('type') != 'FILESYSTEM':
            continue
        if not ((ds.get('special_small_block_size') or {}).get('parsed') or 0):
            continue
        dedup = ds.get('deduplication') or {}
        source = dedup.get('source')
        if source in ('DEFAULT', 'NONE'):
            affected.append(ds['name'])
        elif source == 'INHERITED':
            # Only a value inherited from the dataset being changed or one of its
            # ancestors is masked by the new local value; a value inherited from a
            # dataset in between keeps masking it.
            src = dedup.get('source_info')
            if src is not None and (src == dataset_name or dataset_name.startswith(f'{src}/')):
                affected.append(ds['name'])
    return sorted(affected)


async def validate_dedup_tiering(
    middleware, verrors, schema, deduplication, pool_name, dataset_type,
    special_small_blocks, cur_deduplication=None, dataset_name=None,
):
    """Reject enabling ZFS deduplication where data sits (or would sit) on the SPECIAL vdev.

    Only PERFORMANCE placement (``special_small_blocks`` > 0, so the dataset's data lives
    on the SPECIAL vdev) conflicts with deduplication. REGULAR datasets keep their data on
    the normal vdev and may be deduplicated freely; only FILESYSTEM datasets can be tiered,
    so volumes are never restricted. Datasets that already have deduplication in effect are
    left alone so no-op resubmissions and ON<->VERIFY changes keep working.

    ``dataset_name`` names an existing dataset being updated (None on creation). Because
    deduplication is inherited, enabling it also enables it on every descendant without
    its own deduplication setting, so a PERFORMANCE-placed descendant that would inherit
    the new value blocks the change as well.
    """
    if dataset_type != 'FILESYSTEM':
        return

    if deduplication not in ('ON', 'VERIFY'):
        return

    if cur_deduplication is not None and cur_deduplication.get('value') not in (None, 'OFF'):
        # Deduplication is already in effect on this dataset.
        return

    if not special_small_blocks and dataset_name is None:
        # Creating a dataset with REGULAR placement: its data goes to the normal vdev
        # and it has no descendants yet, safe to deduplicate.
        return

    if not (await middleware.call('zfs.tier.config')).enabled:
        return

    if not await pool_has_special_vdev(middleware, pool_name):
        # Data cannot land on a SPECIAL vdev regardless of placement.
        return

    if special_small_blocks:
        verrors.add(
            f'{schema}.deduplication',
            'ZFS deduplication is incompatible with tiering and cannot be enabled on a dataset '
            'assigned to the PERFORMANCE tier (its data is placed on the SPECIAL vdev); switch it '
            'to the REGULAR tier first.'
        )
        return

    affected = await _dedup_inheriting_performance_descendants(middleware, dataset_name)
    if affected:
        others = f' (and {len(affected) - 1} more)' if len(affected) > 1 else ''
        verrors.add(
            f'{schema}.deduplication',
            'ZFS deduplication is incompatible with tiering and cannot be enabled here: descendant '
            f'dataset {affected[0]!r}{others} is assigned to the PERFORMANCE tier (its data is placed '
            'on the SPECIAL vdev) and would inherit deduplication; switch it to the REGULAR tier first.'
        )


def none_normalize(x):
    if x in (0, None):
        return 'none'
    return x


def _null(x):
    if x == 'none':
        return None
    return x


def dataset_mountpoint(dataset):
    if dataset['mountpoint'] == 'legacy':
        return None

    return dataset['mountpoint'] or os.path.join('/mnt', dataset['name'])


def dataset_can_be_mounted(ds_name, ds_mountpoint):
    mount_error_check = ''
    if os.path.isfile(ds_mountpoint):
        mount_error_check = f'A file exists at {ds_mountpoint!r} and {ds_name} cannot be mounted'
    elif os.path.isdir(ds_mountpoint) and not directory_is_empty(ds_mountpoint):
        mount_error_check = f'{ds_mountpoint!r} directory is not empty'
    mount_error_check += (
        ' (please provide "force" flag to override this error and file/directory '
        'will be renamed once the dataset is unlocked)' if mount_error_check else ''
    )
    return mount_error_check


def retrieve_keys_from_file(job):
    job.check_pipe('input')
    try:
        data = json.loads(job.pipes.input.r.read(10 * MB))
    except json.JSONDecodeError:
        raise CallError('Input file must be a valid JSON file')

    if not isinstance(data, dict) or any(not isinstance(v, str) for v in data.values()):
        raise CallError('Please specify correct format for input file')

    return data


def get_dataset_parents(dataset: str) -> list:
    return [parent.as_posix() for parent in Path(dataset).parents][:-1]


def encryption_root_children(child_list_out: list[dict], encryption_root: str, dataset: dict) -> None:
    """ helper function for generating list of children sharing same encryption root
    that are mount candidates in `pool.dataset.unlock`. """
    for child in dataset['children']:
        if child['mountpoint'] in ('legacy', 'none'):
            # We don't want to forcibly mount a legacy mountpoint here. If we're
            # using these in a plugin we should have logic there to handle where
            # it's supposed to be mounted.
            continue

        if child['encryption_root'] == encryption_root:
            child_list_out.append(child)
            # recursion is OK here since we'll never exceed max ZFS recursion depth
            encryption_root_children(child_list_out, encryption_root, child)


class ZFSKeyFormat(enum.Enum):
    HEX = 'HEX'
    PASSPHRASE = 'PASSPHRASE'
    RAW = 'RAW'


class PropertyDef(typing.NamedTuple):
    api_name: str
    """name we expose to API consumer"""
    real_name: str
    """actual zfs propert name in libzfs"""
    transform: typing.Callable | None
    """callable to transform the value for the property (if required)"""
    inheritable: bool
    """if the zfs property can be inherited"""
    is_user_prop: bool
    """is this property an a zfs USER property instead of a data property"""


POOL_BASE_PROPERTIES = (
    PropertyDef('aclinherit', 'aclinherit', str.lower, True, False),
    PropertyDef('aclmode', 'aclmode', str.lower, True, False),
    PropertyDef('acltype', 'acltype', str.lower, True, False),
    PropertyDef('atime', 'atime', str.lower, True, False),
    PropertyDef('checksum', 'checksum', str.lower, True, False),
    PropertyDef('compression', 'compression', str.lower, True, False),
    PropertyDef('copies', 'copies', str, True, False),
    PropertyDef('deduplication', 'dedup', str.lower, True, False),
    PropertyDef('exec', 'exec', str.lower, True, False),
    PropertyDef('sync', 'sync', str.lower, True, False),
    PropertyDef('quota', 'quota', none_normalize, False, False),
    PropertyDef('readonly', 'readonly', str.lower, True, False),
    PropertyDef('recordsize', 'recordsize', None, True, False),
    PropertyDef('refreservation', 'refreservation', none_normalize, False, False),
    PropertyDef('refquota', 'refquota', none_normalize, False, False),
    PropertyDef('reservation', 'reservation', none_normalize, False, False),
    PropertyDef('snapdev', 'snapdev', str.lower, True, False),
    PropertyDef('snapdir', 'snapdir', str.lower, True, False),
    PropertyDef('special_small_block_size', 'special_small_blocks', None, True, False),
    PropertyDef('volsize', 'volsize', lambda x: str(x), False, False),
    # user properties but obfuscated to the api consumer as zfs properties
    PropertyDef('comments', TNUserProp.DESCRIPTION.value, None, False, True),
    PropertyDef('managedby', TNUserProp.MANAGED_BY.value, None, True, True),
    PropertyDef('quota_warning', TNUserProp.QUOTA_WARN.value, str, True, True),
    PropertyDef('quota_critical', TNUserProp.QUOTA_CRIT.value, str, True, True),
    PropertyDef('refquota_warning', TNUserProp.REFQUOTA_WARN.value, str, True, True),
    PropertyDef('refquota_critical', TNUserProp.REFQUOTA_CRIT.value, str, True, True),

)
POOL_DS_UPDATE_PROPERTIES = POOL_BASE_PROPERTIES
POOL_DS_CREATE_PROPERTIES = POOL_BASE_PROPERTIES + (
    PropertyDef('casesensitivity', 'casesensitivity', str.lower, True, False),
    # sparse is NOT an actual zfs property but is a boolean value we provide
    # during a create request to allow the api consumer the ability to create
    # zvols as "thin" provisioned (i.e. "refreservation" is set to "none" (i.e 0))
    PropertyDef('sparse', 'sparse', None, False, False),
    PropertyDef('volblocksize', 'volblocksize', None, False, False),
)
