from unittest.mock import patch

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.plugins.docker.update import DockerService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize('new_values,old_values,error_msgs', [
    (
        {
            'pool': 'tank',
            'address_pools': [],
            'secure_registry_mirrors': ['https://mirror1.example.com', 'https://mirror2.example.com'],
            'insecure_registry_mirrors': ['http://insecure1.example.com', 'http://insecure2.example.com'],
        },
        {
            'pool': 'tank',
            'address_pools': [],
            'secure_registry_mirrors': [],
            'insecure_registry_mirrors': [],
        },
        []
    ),
    (
        {
            'pool': 'tank',
            'address_pools': [],
            'secure_registry_mirrors': ['https://mirror1.example.com', 'https://mirror1.example.com'],
            'insecure_registry_mirrors': [],
        },
        {
            'pool': 'tank',
            'address_pools': [],
            'secure_registry_mirrors': [],
            'insecure_registry_mirrors': [],
        },
        ['Duplicate secure registry mirror.']
    ),
    (
        {
            'pool': 'tank',
            'address_pools': [],
            'secure_registry_mirrors': [],
            'insecure_registry_mirrors': ['http://insecure1.example.com', 'http://insecure1.example.com'],
        },
        {
            'pool': 'tank',
            'address_pools': [],
            'secure_registry_mirrors': [],
            'insecure_registry_mirrors': [],
        },
        ['Duplicate insecure registry mirror.']
    ),
    (
        {
            'pool': 'tank',
            'address_pools': [],
            'secure_registry_mirrors': ['https://mirror1.example.com'],
            'insecure_registry_mirrors': ['https://mirror1.example.com'],
        },
        {
            'pool': 'tank',
            'address_pools': [],
            'secure_registry_mirrors': [],
            'insecure_registry_mirrors': [],
        },
        ['Registry mirror https://mirror1.example.com cannot be in both secure and insecure lists.']
    ),
])
@pytest.mark.asyncio
async def test_docker_registry_mirrors_validation(new_values, old_values, error_msgs):
    m = Middleware()
    m['interface.ip_in_use'] = lambda *arg: []
    m['system.is_ha_capable'] = lambda *arg: False

    with patch('middlewared.plugins.docker.update.query_imported_fast_impl') as run:
        run.return_value = {'5714764211007133142': {'name': 'tank', 'state': 'ONLINE'}}

        if not error_msgs:
            assert await DockerService(m).validate_data(old_values, new_values) is None
        else:
            with pytest.raises(ValidationErrors) as ve:
                await DockerService(m).validate_data(old_values, new_values)
            for i in range(len(error_msgs)):
                assert ve.value.errors[i].errmsg == error_msgs[i]
