import os

from middlewared.plugins.vm.utils import LIBVIRT_QEMU_UID, LIBVIRT_QEMU_GID

from .utils import SYSDATASET_PATH


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
                        'gid': {'type': 'integer'}
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
                'mountpoint': 'legacy',
                'readonly': 'off',
                'snapdir': 'hidden',
            },
            'mountpoint': SYSDATASET_PATH,
            'chown_config': {
                'uid': 0,
                'gid': 0,
                'mode': 0o755,
            },
        },
        {
            'name': os.path.join(pool_name, '.system/cores'),
            'props': {
                'mountpoint': 'legacy',
                'readonly': 'off',
                'snapdir': 'hidden',
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
                'mountpoint': 'legacy',
                'readonly': 'off',
                'snapdir': 'hidden',
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
                'mountpoint': 'legacy',
                'readonly': 'off',
                'snapdir': 'hidden',
            },
            'chown_config': {
                'uid': 0,
                'gid': 0,
                'mode': 0o755,
            },
        },
        {
            'name': os.path.join(pool_name, '.system/vm'),
            'props': {
                'mountpoint': 'legacy',
                'readonly': 'off',
                'snapdir': 'hidden',
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
            ],
        },
        {
            'name': os.path.join(pool_name, f'.system/configs-{uuid}'),
            'props': {
                'mountpoint': 'legacy',
                'readonly': 'off',
                'snapdir': 'hidden',
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
                'mountpoint': 'legacy',
                'readonly': 'off',
                'snapdir': 'hidden',
                'canmount': 'noauto',
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
