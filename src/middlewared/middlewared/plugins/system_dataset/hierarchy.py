from enum import StrEnum
import os

from middlewared.plugins.vm.utils import LIBVIRT_QEMU_GID, LIBVIRT_QEMU_UID
from middlewared.utils.boot.pool import BOOT_POOL_NAME_VALID

from .utils import SYSDATASET_PATH


class SystemDatasetZfsProperties(StrEnum):
    ATIME = 'atime'
    CANMOUNT = 'canmount'
    MOUNTPOINT = 'mountpoint'
    PREFETCH = 'prefetch'
    PRIMARYCACHE = 'primarycache'
    READONLY = 'readonly'
    RECORDSIZE = 'recordsize'
    SECONDARYCACHE = 'secondarycache'
    SNAPDIR = 'snapdir'


SYSTEM_DATASET_JSON_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'description': 'Schema for the output of get_system_dataset_spec function',
    'type': 'array',
    'items': {
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string'
            },
            'props': {
                'type': 'object',
                'properties': {
                    'mountpoint': {
                        'type': 'string',
                        'const': 'legacy'
                    },
                    'readonly': {
                        'type': 'string',
                        'const': 'off'
                    },
                    'snapdir': {
                        'type': 'string',
                        'const': 'hidden'
                    },
                    'canmount': {'type': 'string'},
                },
                'required': ['mountpoint', 'readonly', 'snapdir'],
            },
            'chown_config': {
                'type': 'object',
                'properties': {
                    'uid': {'type': 'integer'},
                    'gid': {'type': 'integer'},
                    'mode': {'type': 'integer'},
                },
                'required': ['uid', 'gid', 'mode'],
            },
            'mountpoint': {
                'type': 'string'
            },
            'create_paths': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'path': {'type': 'string'},
                        'uid': {'type': 'integer'},
                        'gid': {'type': 'integer'},
                        'mode': {'type': 'integer'}
                    },
                    'required': ['path', 'uid', 'gid']
                }
            },
            'post_mount_actions': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'method': {'type': 'string'},
                        'args': {
                            'type': 'array',
                            'items': {'type': 'string'},
                        },
                    },
                    'required': ['method']
                }
            },
            'pwenc_encrypted': {'type': 'boolean'},
        },
        'required': ['name', 'props', 'chown_config'],
        'additionalProperties': False,
    }
}


# These are the properties of a dataset that holds an LMDB store. The tiering dataset and the TrueSearch index dataset
# use them. Each spec gets a copy, because setup_datasets changes the properties of a spec.
MDBSTORE_PROPS = {
    SystemDatasetZfsProperties.ATIME: 'off',
    SystemDatasetZfsProperties.MOUNTPOINT: 'legacy',
    SystemDatasetZfsProperties.READONLY: 'off',
    SystemDatasetZfsProperties.SNAPDIR: 'hidden',
    SystemDatasetZfsProperties.PREFETCH: 'none',
    SystemDatasetZfsProperties.PRIMARYCACHE: 'metadata',
    SystemDatasetZfsProperties.SECONDARYCACHE: 'none',
    SystemDatasetZfsProperties.RECORDSIZE: '32k',
}


def get_system_dataset_spec(pool_name: str, uuid: str) -> list:
    spec = [
        {
            'name': os.path.join(pool_name, '.system'),
            'props': {
                SystemDatasetZfsProperties.MOUNTPOINT: 'legacy',
                SystemDatasetZfsProperties.READONLY: 'off',
                SystemDatasetZfsProperties.SNAPDIR: 'hidden',
            },
            'mountpoint': SYSDATASET_PATH,
            'chown_config': {
                'uid': 0,
                'gid': 0,
                'mode': 0o755,
            },
            'create_paths': [
                {
                    'path': '/var/db/system/directory_services',
                    'uid': 0,
                    'gid': 0,
                    'mode': 0o700
                },
            ],
        },
        {
            'name': os.path.join(pool_name, '.system/cores'),
            'props': {
                SystemDatasetZfsProperties.MOUNTPOINT: 'legacy',
                SystemDatasetZfsProperties.READONLY: 'off',
                SystemDatasetZfsProperties.SNAPDIR: 'hidden',
            },
            'chown_config': {
                'uid': 0,
                'gid': 0,
                'mode': 0o755,
            },
        },
        {
            'name': os.path.join(pool_name, '.system/nfs'),
            'props': {
                SystemDatasetZfsProperties.MOUNTPOINT: 'legacy',
                SystemDatasetZfsProperties.READONLY: 'off',
                SystemDatasetZfsProperties.SNAPDIR: 'hidden',
            },
            'chown_config': {
                'uid': 0,
                'gid': 0,
                'mode': 0o755,
            },
            'post_mount_actions': [
                {
                    'method': 'nfs.setup_directories',
                    'args': [],
                }
            ]
        },
        {
            'name': os.path.join(pool_name, '.system/samba4'),
            'props': {
                SystemDatasetZfsProperties.MOUNTPOINT: 'legacy',
                SystemDatasetZfsProperties.READONLY: 'off',
                SystemDatasetZfsProperties.SNAPDIR: 'hidden',
            },
            'chown_config': {
                'uid': 0,
                'gid': 0,
                'mode': 0o755,
            },
        },
        {
            'name': os.path.join(pool_name, '.system/truenas_zfstierd'),
            'props': {**MDBSTORE_PROPS},
            'chown_config': {
                'uid': 0,
                'gid': 0,
                'mode': 0o700,
            },
        },
        {
            # truesearch-indexer keeps an index for each indexed dataset here. Both daemons run as root.
            # The indexes also hold the names, tags and comments of files in encrypted datasets. So the pwenc secret
            # encrypts this dataset. See systemdataset.setup_datasets.
            # Both daemons map the indexes into memory and read 4 KiB pages at random. A small record makes a page
            # fault cheaper. With primarycache=metadata, the ARC does not keep a second copy of the pages in the page
            # cache.
            'name': os.path.join(pool_name, '.system/truesearchd'),
            'props': {**MDBSTORE_PROPS},
            'pwenc_encrypted': True,
            'chown_config': {
                'uid': 0,
                'gid': 0,
                'mode': 0o700,
            },
            'post_mount_actions': [
                {
                    'method': 'truesearch.configure',
                    'args': [],
                }
            ]
        },
        {
            'name': os.path.join(pool_name, '.system/vm'),
            'props': {
                SystemDatasetZfsProperties.MOUNTPOINT: 'legacy',
                SystemDatasetZfsProperties.READONLY: 'off',
                SystemDatasetZfsProperties.SNAPDIR: 'hidden',
            },
            'chown_config': {
                'uid': LIBVIRT_QEMU_UID,
                'gid': LIBVIRT_QEMU_GID,
                'mode': 0o755,
            },
            'create_paths': [
                {
                    'path': '/var/db/system/vm/nvram',
                    'uid': LIBVIRT_QEMU_UID,
                    'gid': LIBVIRT_QEMU_GID
                },
                {
                    'path': '/var/db/system/vm/tpm',
                    'uid': LIBVIRT_QEMU_UID,
                    'gid': LIBVIRT_QEMU_GID
                },
            ],
        },
        {
            'name': os.path.join(pool_name, '.system/webshare'),
            'props': {
                SystemDatasetZfsProperties.MOUNTPOINT: 'legacy',
                SystemDatasetZfsProperties.READONLY: 'off',
                SystemDatasetZfsProperties.SNAPDIR: 'hidden',
            },
            'chown_config': {
                'uid': 0,
                'gid': 0,
                'mode': 0o700,
            },
            'post_mount_actions': [
                {
                    'method': 'webshare.setup_directories',
                    'args': [],
                }
            ]
        },
        {
            'name': os.path.join(pool_name, f'.system/configs-{uuid}'),
            'props': {
                SystemDatasetZfsProperties.MOUNTPOINT: 'legacy',
                SystemDatasetZfsProperties.READONLY: 'off',
                SystemDatasetZfsProperties.SNAPDIR: 'hidden',
            },
            'chown_config': {
                'uid': 0,
                'gid': 0,
                'mode': 0o755,
            },
        },
        {
            'name': os.path.join(pool_name, f'.system/netdata-{uuid}'),
            'props': {
                SystemDatasetZfsProperties.MOUNTPOINT: 'legacy',
                SystemDatasetZfsProperties.READONLY: 'off',
                SystemDatasetZfsProperties.SNAPDIR: 'hidden',
                SystemDatasetZfsProperties.CANMOUNT: 'noauto',
            },
            'chown_config': {
                'uid': 999,
                'gid': 997,
                'mode': 0o755,
            },
            'mountpoint': os.path.join(SYSDATASET_PATH, 'netdata'),
            'create_paths': [
                {'path': '/var/log/netdata', 'uid': 999, 'gid': 997},
            ],
            'post_mount_actions': [
                {
                    'method': 'reporting.post_dataset_mount_action',
                    'args': [],
                }
            ]
        },
    ]
    # The boot pool cannot hold an encrypted dataset. The installer makes it with compatibility=grub2, which leaves
    # the encryption feature disabled. So a dataset that the pwenc secret encrypts is only on a data pool.
    if pool_name in BOOT_POOL_NAME_VALID:
        spec = [ds for ds in spec if not ds.get('pwenc_encrypted')]

    return spec
