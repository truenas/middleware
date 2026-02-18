import os
from enum import StrEnum

from middlewared.plugins.vm.utils import LIBVIRT_QEMU_UID, LIBVIRT_QEMU_GID
from middlewared.utils.truesearch import TRUESEARCH_UID, TRUESEARCH_GID

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
        },
        'required': ['name', 'props', 'chown_config'],
        'additionalProperties': False,
    }
}


def get_system_dataset_spec(pool_name: str, uuid: str) -> list:
    return [
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
            'create_paths': [
                {'path': '/var/db/system/samba4/lock', 'uid': 0, 'gid': 0},
            ],
        },
        {
            'name': os.path.join(pool_name, '.system/truenas_zfsrewrited'),
            'props': {
                SystemDatasetZfsProperties.ATIME: 'off',
                SystemDatasetZfsProperties.MOUNTPOINT: 'legacy',
                SystemDatasetZfsProperties.READONLY: 'off',
                SystemDatasetZfsProperties.SNAPDIR: 'hidden',
                SystemDatasetZfsProperties.PREFETCH: 'none',
                SystemDatasetZfsProperties.PRIMARYCACHE: 'metadata',
                SystemDatasetZfsProperties.SECONDARYCACHE: 'none',
                SystemDatasetZfsProperties.RECORDSIZE: '32k',
            },
            'chown_config': {
                'uid': 0,
                'gid': 0,
                'mode': 0o700,
            },
        },
        {
            'name': os.path.join(pool_name, '.system/truesearch'),
            'props': {
                SystemDatasetZfsProperties.MOUNTPOINT: 'legacy',
                SystemDatasetZfsProperties.READONLY: 'off',
                SystemDatasetZfsProperties.SNAPDIR: 'hidden',
            },
            'chown_config': {
                'uid': TRUESEARCH_UID,
                'gid': TRUESEARCH_GID,
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
