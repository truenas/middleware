from unittest.mock import patch

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.plugins.docker.update import DockerService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.utils import filter_list


SYSTEM_STATE = {
    'available_pool': ['test', 'tank'],
    'available_dataset': [
        {
            'id': 'tank/ix-apps',
            'encrypted': False,
        }
    ],
    'pool_quick_info': {
        'key_format': {
            'value': None,
        },
        'locked': False
    },
    'import_query_pool': {'5714764211007133142': {'name': 'tank', 'state': 'ONLINE'}},
    'available_keys': []
}


@pytest.mark.parametrize('system_state,new_values,old_values,error_msgs', [
    (
        SYSTEM_STATE,
        {
            'pool': 'test',
            'address_pools': [],
            'migrate_applications': True,
        },
        {
            'pool': 'tank',
            'address_pools': [],
        },
        []
    ),
    (
        {
            **SYSTEM_STATE,
            'import_query_pool': {}
        },
        {
            'pool': 'test',
            'address_pools': [],
            'migrate_applications': True,
        },
        {
            'pool': 'tank',
            'address_pools': [],
        },
        ['Pool not found.']
    ),
    (
        SYSTEM_STATE,
        {
            'pool': 'tank',
            'address_pools': [],
            'migrate_applications': True,
        },
        {
            'pool': 'tank',
            'address_pools': [],
        },
        ['Migration of applications dataset only happens when a new pool is configured.']
    ),
    (
        SYSTEM_STATE,
        {
            'pool': 'tank',
            'address_pools': [],
            'migrate_applications': True,
        },
        {
            'pool': None,
            'address_pools': [],
        },
        ['A pool must have been configured previously for ix-apps dataset migration.']
    ),
    (
        {
            **SYSTEM_STATE,
            'available_dataset': [
                {'id': 'tank/ix-apps', 'encrypted': False},
                {'id': 'test/ix-apps', 'encrypted': False}
            ],

        },
        {
            'pool': 'test',
            'address_pools': [],
            'migrate_applications': True,
        },
        {
            'pool': 'tank',
            'address_pools': [],
        },
        ['Migration of \'tank/ix-apps\' to \'test\' not possible as test/ix-apps already exists.']
    ),
    (
        {
            **SYSTEM_STATE,
            'available_dataset': [],

        },
        {
            'pool': 'test',
            'address_pools': [],
            'migrate_applications': True,
        },
        {
            'pool': 'tank',
            'address_pools': [],
        },
        ['\'tank/ix-apps\' does not exist, migration not possible.']
    ),
    (
        {
            **SYSTEM_STATE,
            'available_dataset': [
                {'id': 'tank/ix-apps', 'encrypted': True},
            ],

        },
        {
            'pool': 'test',
            'address_pools': [],
            'migrate_applications': True,
        },
        {
            'pool': 'tank',
            'address_pools': [],
        },
        ['\'tank/ix-apps\' is encrypted which is not a supported configuration']
    ),
    (
        {
            **SYSTEM_STATE,
            'pool_quick_info': {
                'key_format': {
                    'value': 'PASSPHRASE',
                },
                'locked': False
            },
        },
        {
            'pool': 'test',
            'address_pools': [],
            'migrate_applications': True,
        },
        {
            'pool': 'tank',
            'address_pools': [],
        },
        ['\'tank/ix-apps\' can only be migrated to a destination pool which is "KEY" encrypted.']
    ),
    (
        {
            **SYSTEM_STATE,
            'pool_quick_info': {
                'key_format': {
                    'value': 'AES-256-GCM',
                },
                'locked': False
            },
        },
        {
            'pool': 'test',
            'address_pools': [],
            'migrate_applications': True,
        },
        {
            'pool': 'tank',
            'address_pools': [],
        },
        []
    ),
    (
        {
            **SYSTEM_STATE,
            'pool_quick_info': {
                'key_format': {
                    'value': 'AES-256-GCM',
                },
                'locked': True
            },
            'available_keys': [
                {
                   'id': 2,
                   'name': 'test',
                   'encryption_key': 'de06572a58e834985cafecb0e56756a24db77a6512817d1f8f93b4346b7979e0',
                   'kmip_uid': None
                }
            ]
        },
        {
            'pool': 'test',
            'address_pools': [],
            'migrate_applications': True,
        },
        {
            'pool': 'tank',
            'address_pools': [],
        },
        ['Migration not possible as \'test\' is locked']
    ),
    (
        {
            **SYSTEM_STATE,
            'pool_quick_info': {
                'key_format': {
                    'value': 'AES-256-GCM',
                },
                'locked': True
            },
        },
        {
            'pool': 'test',
            'address_pools': [],
            'migrate_applications': True,
        },
        {
            'pool': 'tank',
            'address_pools': [],
        },
        [
            'Migration not possible as \'test\' is locked',
            'Migration not possible as system does not has encryption key for \'test\' stored'
        ]
    ),
])
@pytest.mark.asyncio
async def test_docker_update_validation(system_state, new_values, old_values, error_msgs):
    m = Middleware()
    m['interface.ip_in_use'] = lambda *arg: []
    m['datastore.query'] = lambda *arg: system_state['available_keys']
    m['zfs.dataset.query'] = lambda *arg: filter_list(system_state['available_dataset'], arg[0])
    m['pool.dataset.get_instance_quick'] = lambda *arg: system_state['pool_quick_info']
    with patch('middlewared.plugins.docker.update.query_imported_fast_impl') as run:
        run.return_value = system_state['import_query_pool']
        if not error_msgs:
            assert await DockerService(m).validate_data(old_values, new_values) is None
        else:
            with pytest.raises(ValidationErrors) as ve:
                await DockerService(m).validate_data(old_values, new_values)
            for i in range(len(error_msgs)):
                assert ve.value.errors[i].errmsg == error_msgs[i]
