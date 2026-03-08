import logging
from unittest.mock import patch

import pytest

from middlewared.api.current import DockerEntry, ZFSResourceQuery
from middlewared.service.context import ServiceContext
from middlewared.service_exception import ValidationErrors
from middlewared.plugins.docker.config import DockerConfigServicePart
from middlewared.pytest.unit.middleware import Middleware


def make_svc_part(m):
    context = ServiceContext(m, logging.getLogger('test'))
    return DockerConfigServicePart(context)


def mock_zfs_resource_query_impl(system_state):
    """Create a mock function for zfs.resource.query_impl."""
    def _query_impl(args):
        paths = args.paths
        if not paths:
            return []

        path = paths[0]
        requested_properties = args.properties

        # Check if it's querying for ix-apps dataset
        if path.endswith('/ix-apps'):
            # Look for matching dataset in available_dataset
            for ds in system_state.get('available_dataset', []):
                if ds['name'] == path:
                    # If specific properties are requested, ensure they exist
                    if requested_properties and 'encryption' in requested_properties:
                        if 'encryption' not in ds.get('properties', {}):
                            ds['properties']['encryption'] = {'raw': 'off'}
                    return [ds]
            return []

        # Check if it's querying for a pool
        if '/' not in path and 'pool_resources' in system_state:
            for pool in system_state['pool_resources']:
                if pool['name'] == path:
                    # If specific properties are requested, ensure they exist
                    if requested_properties:
                        for prop in requested_properties:
                            if prop not in pool.get('properties', {}):
                                # Add default values for missing properties
                                if prop == 'encryption':
                                    pool['properties']['encryption'] = {'raw': 'off'}
                                elif prop == 'keyformat':
                                    pool['properties']['keyformat'] = {'raw': 'none'}
                                elif prop == 'keystatus':
                                    pool['properties']['keystatus'] = {'raw': 'available'}
                    return [pool]
            return []

        return []

    return _query_impl


DEFAULTS = dict(id=1, enable_image_updates=True, nvidia=False, cidr_v6='fdd0::/64', registry_mirrors=[])

SYSTEM_STATE = {
    'available_pool': ['test', 'tank'],
    'available_dataset': [
        {
            'name': 'tank/ix-apps',
            'properties': {
                'encryption': {'raw': 'off'},
                'keyformat': {'raw': 'none'},
                'keystatus': {'raw': 'available'},
                'keylocation': {'raw': 'prompt'},
            }
        }
    ],
    'pool_resources': [
        {
            'name': 'test',
            'properties': {
                'encryption': {'raw': 'off'},
                'keyformat': {'raw': 'none'},
                'keystatus': {'raw': 'available'},
                'keylocation': {'raw': 'prompt'},
            }
        },
        {
            'name': 'tank',
            'properties': {
                'encryption': {'raw': 'off'},
                'keyformat': {'raw': 'none'},
                'keystatus': {'raw': 'available'},
                'keylocation': {'raw': 'prompt'},
            }
        }
    ],
    'import_query_pool': {'5714764211007133142': {'name': 'tank', 'state': 'ONLINE'}},
    'available_keys': []
}


@pytest.mark.parametrize('system_state,new_config,old_config,migrate_apps,error_msgs', [
    (
        SYSTEM_STATE,
        DockerEntry.model_construct(**DEFAULTS, pool='test', dataset='test/ix-apps', address_pools=[]),
        DockerEntry.model_construct(**DEFAULTS, pool='tank', dataset='tank/ix-apps', address_pools=[]),
        True,
        []
    ),
    (
        {
            **SYSTEM_STATE,
            'import_query_pool': {}
        },
        DockerEntry.model_construct(**DEFAULTS, pool='test', dataset='test/ix-apps', address_pools=[]),
        DockerEntry.model_construct(**DEFAULTS, pool='tank', dataset='tank/ix-apps', address_pools=[]),
        True,
        ['Pool not found.']
    ),
    (
        SYSTEM_STATE,
        DockerEntry.model_construct(**DEFAULTS, pool='tank', dataset='tank/ix-apps', address_pools=[]),
        DockerEntry.model_construct(**DEFAULTS, pool='tank', dataset='tank/ix-apps', address_pools=[]),
        True,
        ['Migration of applications dataset only happens when a new pool is configured.']
    ),
    (
        SYSTEM_STATE,
        DockerEntry.model_construct(**DEFAULTS, pool='tank', dataset='tank/ix-apps', address_pools=[]),
        DockerEntry.model_construct(**DEFAULTS, pool=None, dataset=None, address_pools=[]),
        True,
        ['A pool must have been configured previously for ix-apps dataset migration.']
    ),
    (
        {
            **SYSTEM_STATE,
            'available_dataset': [
                {
                    'name': 'tank/ix-apps',
                    'properties': {
                        'encryption': {'raw': 'off'},
                        'keyformat': {'raw': 'none'},
                        'keystatus': {'raw': 'available'},
                        'keylocation': {'raw': 'prompt'},
                    }
                },
                {
                    'name': 'test/ix-apps',
                    'properties': {
                        'encryption': {'raw': 'off'},
                        'keyformat': {'raw': 'none'},
                        'keystatus': {'raw': 'available'},
                        'keylocation': {'raw': 'prompt'},
                    }
                }
            ],

        },
        DockerEntry.model_construct(**DEFAULTS, pool='test', dataset='test/ix-apps', address_pools=[]),
        DockerEntry.model_construct(**DEFAULTS, pool='tank', dataset='tank/ix-apps', address_pools=[]),
        True,
        ['Migration of \'tank/ix-apps\' to \'test\' not possible as test/ix-apps already exists.']
    ),
    (
        {
            **SYSTEM_STATE,
            'available_dataset': [],

        },
        DockerEntry.model_construct(**DEFAULTS, pool='test', dataset='test/ix-apps', address_pools=[]),
        DockerEntry.model_construct(**DEFAULTS, pool='tank', dataset='tank/ix-apps', address_pools=[]),
        True,
        ['\'tank/ix-apps\' does not exist, migration not possible.']
    ),
    (
        {
            **SYSTEM_STATE,
            'available_dataset': [
                {
                    'name': 'tank/ix-apps',
                    'properties': {
                        'encryption': {'raw': 'aes-256-gcm'},
                        'keyformat': {'raw': 'none'},
                        'keystatus': {'raw': 'available'},
                        'keylocation': {'raw': 'prompt'},
                    }
                },
            ],

        },
        DockerEntry.model_construct(**DEFAULTS, pool='test', dataset='test/ix-apps', address_pools=[]),
        DockerEntry.model_construct(**DEFAULTS, pool='tank', dataset='tank/ix-apps', address_pools=[]),
        True,
        ['\'tank/ix-apps\' is encrypted which is not a supported configuration']
    ),
    (
        {
            **SYSTEM_STATE,
            'pool_resources': [
                {
                    'name': 'test',
                    'properties': {
                        'encryption': {'raw': 'aes-256-gcm'},
                        'keyformat': {'raw': 'passphrase'},
                        'keystatus': {'raw': 'available'},
                        'keylocation': {'raw': 'prompt'},
                    }
                }
            ],
        },
        DockerEntry.model_construct(**DEFAULTS, pool='test', dataset='test/ix-apps', address_pools=[]),
        DockerEntry.model_construct(**DEFAULTS, pool='tank', dataset='tank/ix-apps', address_pools=[]),
        True,
        ['\'tank/ix-apps\' can only be migrated to a destination pool which is "KEY" encrypted.']
    ),
    (
        {
            **SYSTEM_STATE,
            'pool_resources': [
                {
                    'name': 'test',
                    'properties': {
                        'encryption': {'raw': 'aes-256-gcm'},
                        'keyformat': {'raw': 'hex'},
                        'keystatus': {'raw': 'available'},
                        'keylocation': {'raw': 'prompt'},
                    }
                }
            ],
            'available_keys': [
                {
                    'id': 1,
                    'name': 'test',
                    'encryption_key': 'de06572a58e834985cafecb0e56756a24db77a6512817d1f8f93b4346b7979e0',
                    'kmip_uid': None
                }
            ]
        },
        DockerEntry.model_construct(**DEFAULTS, pool='test', dataset='test/ix-apps', address_pools=[]),
        DockerEntry.model_construct(**DEFAULTS, pool='tank', dataset='tank/ix-apps', address_pools=[]),
        True,
        []
    ),
    (
        {
            **SYSTEM_STATE,
            'pool_resources': [
                {
                    'name': 'test',
                    'properties': {
                        'encryption': {'raw': 'aes-256-gcm'},
                        'keyformat': {'raw': 'hex'},
                        'keystatus': {'raw': 'unavailable'},
                        'keylocation': {'raw': 'prompt'},
                    }
                }
            ],
            'available_keys': [
                {
                    'id': 2,
                    'name': 'test',
                    'encryption_key': 'de06572a58e834985cafecb0e56756a24db77a6512817d1f8f93b4346b7979e0',
                    'kmip_uid': None
                }
            ]
        },
        DockerEntry.model_construct(**DEFAULTS, pool='test', dataset='test/ix-apps', address_pools=[]),
        DockerEntry.model_construct(**DEFAULTS, pool='tank', dataset='tank/ix-apps', address_pools=[]),
        True,
        ['Migration not possible as \'test\' is locked']
    ),
    (
        {
            **SYSTEM_STATE,
            'pool_resources': [
                {
                    'name': 'test',
                    'properties': {
                        'encryption': {'raw': 'aes-256-gcm'},
                        'keyformat': {'raw': 'hex'},
                        'keystatus': {'raw': 'unavailable'},
                        'keylocation': {'raw': 'prompt'},
                    }
                }
            ],
        },
        DockerEntry.model_construct(**DEFAULTS, pool='test', dataset='test/ix-apps', address_pools=[]),
        DockerEntry.model_construct(**DEFAULTS, pool='tank', dataset='tank/ix-apps', address_pools=[]),
        True,
        [
            'Migration not possible as \'test\' is locked',
            'Migration not possible as system does not has encryption key for \'test\' stored'
        ]
    ),
])
@pytest.mark.asyncio
async def test_docker_update_validation(system_state, new_config, old_config, migrate_apps, error_msgs):
    m = Middleware()
    m['interface.ip_in_use'] = lambda *arg: []
    m['datastore.query'] = lambda *arg: system_state['available_keys']
    m.services.zfs.resource.query_impl = mock_zfs_resource_query_impl(system_state)
    m['system.is_ha_capable'] = lambda *arg: False
    svc_part = make_svc_part(m)
    with patch('middlewared.plugins.docker.config.query_imported_fast_impl') as run:
        run.return_value = system_state['import_query_pool']
        if not error_msgs:
            assert await svc_part.validate(old_config, new_config, migrate_apps) is None
        else:
            with pytest.raises(ValidationErrors) as ve:
                await svc_part.validate(old_config, new_config, migrate_apps)
            for i in range(len(error_msgs)):
                assert ve.value.errors[i].errmsg == error_msgs[i]
