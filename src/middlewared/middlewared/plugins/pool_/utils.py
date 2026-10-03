import enum
import json
import os
from pathlib import Path
import re
import typing
from typing import TypedDict

from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.zfs.utils import get_encryption_info
from middlewared.plugins.zfs_.utils import TNUserProp
from middlewared.service_exception import CallError
from middlewared.utils.filesystem.directory import directory_is_empty
from middlewared.utils.size import MB

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware
    from middlewared.service_exception import ValidationErrors

DATASET_DATABASE_MODEL_NAME = 'storage.encrypteddataset'
RE_DRAID_DATA_DISKS = re.compile(r':\d*d')
RE_DRAID_SPARE_DISKS = re.compile(r':\d*s')
RE_DRAID_NAME = re.compile(r'draid\d:\d+d:\d+c:\d+s-\d+')
RE_ZFS_USER_PROP = re.compile(r'[a-z0-9:._-]+')
ZFS_USER_PROP_MAX_LEN = 255
ZFS_ENCRYPTION_ALGORITHM = 'aes-256-gcm'
ZPOOL_CACHE_FILE = '/data/zfs/zpool.cache'
ZPOOL_KILLCACHE = '/data/zfs/killcache'


class UpdateImplArgs(TypedDict, total=False):
    name: str
    zprops: dict[str, str]
    uprops: dict[str, str]
    iprops: set
    """ZFS properties to be inherited from parent."""


async def validate_dedup_license(
    middleware: 'Middleware', verrors: 'ValidationErrors', schema: str, deduplication: str | None,
) -> None:
    """Reject enabling ZFS deduplication on systems that are not entitled to it.

    Licensed systems must carry the DEDUP feature flag; unlicensed TrueNAS hardware
    (iX-branded, excluding minis) is blocked; Community Edition and minis may use
    dedup freely. Only ON/VERIFY are gated.
    """
    if deduplication not in ('ON', 'VERIFY'):
        return

    entitlement = await middleware.call2(middleware.services.truenas.entitlements.check, LicenseFeature.DEDUP)
    if not entitlement.entitled:
        verrors.add(f'{schema}.deduplication', entitlement.message)


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


def pool_dataset_view(row, encryption=True):
    props = row['properties']
    view = {
        'name': row['name'],
        'type': row['type'],
        'mountpoint': props['mountpoint']['raw'] if row['type'] == 'FILESYSTEM' else None,
        'children': [],
    }
    if not encryption:
        return view

    enc = get_encryption_info(props)
    return view | {
        'encrypted': enc.encrypted,
        'locked': enc.locked,
        'key_loaded': enc.encrypted and not enc.locked,
        'encryption_root': props['encryptionroot']['value'] if enc.encrypted else None,
        'key_format': {
            'value': enc.encryption_type.upper() if enc.encryption_type else None,
            'parsed': props['keyformat']['raw'],
        },
    }


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
    PropertyDef('volblocksize', 'volblocksize', None, False, False),
)
