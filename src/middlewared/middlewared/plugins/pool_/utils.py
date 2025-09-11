import collections
import enum
import itertools
import json
import os
import re

from pathlib import Path

from middlewared.plugins.zfs_.utils import TNUserProp
from middlewared.service_exception import CallError
from middlewared.utils.size import MB
from middlewared.utils.filesystem.directory import directory_is_empty


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


def get_props_of_interest_mapping():
    return [
        (TNUserProp.DESCRIPTION.value, 'comments', None),
        (TNUserProp.QUOTA_WARN.value, 'quota_warning', None),
        (TNUserProp.QUOTA_CRIT.value, 'quota_critical', None),
        (TNUserProp.REFQUOTA_WARN.value, 'refquota_warning', None),
        (TNUserProp.REFQUOTA_CRIT.value, 'refquota_critical', None),
        (TNUserProp.MANAGED_BY.value, 'managedby', None),
        ('dedup', 'deduplication', str.upper),
        ('mountpoint', None, _null),
        ('aclmode', None, str.upper),
        ('acltype', None, str.upper),
        ('xattr', None, str.upper),
        ('atime', None, str.upper),
        ('casesensitivity', None, str.upper),
        ('checksum', None, str.upper),
        ('exec', None, str.upper),
        ('sync', None, str.upper),
        ('compression', None, str.upper),
        ('compressratio', None, None),
        ('origin', None, None),
        ('quota', None, _null),
        ('refquota', None, _null),
        ('reservation', None, _null),
        ('refreservation', None, _null),
        ('copies', None, None),
        ('snapdir', None, str.upper),
        ('readonly', None, str.upper),
        ('recordsize', None, None),
        ('sparse', None, None),
        ('volsize', None, None),
        ('volblocksize', None, None),
        ('keyformat', 'key_format', lambda o: o.upper() if o != 'none' else None),
        ('encryption', 'encryption_algorithm', lambda o: o.upper() if o != 'off' else None),
        ('used', None, None),
        ('usedbychildren', None, None),
        ('usedbydataset', None, None),
        ('usedbyrefreservation', None, None),
        ('usedbysnapshots', None, None),
        ('available', None, None),
        ('special_small_blocks', 'special_small_block_size', None),
        ('pbkdf2iters', None, None),
        ('creation', None, None),
        ('snapdev', None, str.upper),
    ]


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


class ZFSKeyFormat(enum.Enum):
    HEX = 'HEX'
    PASSPHRASE = 'PASSPHRASE'
    RAW = 'RAW'


PropertyDef = collections.namedtuple(
    'PropertyDef',
    (
        'api_name',  # name we expose to API consumer
        'real_name',  # actual zfs property name in libzfs
        'transform',  # how to transform the API name (if needed)
        'inheritable',  # can the zfs property be inherited
        'is_user_prop'  # zfs _USER_ property obfuscated as a zfs property to API consumer
    )
)
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
POOL_DS_CREATE_PROPERTIES = (
    PropertyDef('casesensitivity', 'casesensitivity', str.lower, True, False),
    # sparse is NOT an actual zfs property but is a boolean value we provide
    # during a create request to allow the api consumer the ability to create
    # zvols as "thin" provisioned (i.e. "refreservation" is set to "none" (i.e 0))
    PropertyDef('sparse', 'sparse', None, False, False),
    PropertyDef('volblocksize', 'volblocksize', None, False, False),
)
