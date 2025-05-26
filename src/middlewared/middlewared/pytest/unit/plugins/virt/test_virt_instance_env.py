import unittest.mock

import pytest

from middlewared.plugins.virt.instance import VirtInstanceService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import ValidationErrors


@pytest.mark.parametrize('environment, should_work', [
    (
        {'': ''},
        False
    ),
    (
        {'FOO': ''},
        False
    ),
    (
        {'FOO': '  '},
        False
    ),
    (
        {'': 'BAR'},
        False
    ),
    (
        {'    ': '    '},
        False
    ),
    (
        {'FOO': 'BAR'},
        True
    ),
    (
        {'FOO': 'bar'},
        True
    ),
    (
        {'local_host': '127.0.0.1'},
        True
    ),
    (
        {'123_ABC': 'XYZ'},
        True
    ),
    (
        {'WORKING_DIR': '/home/user'},
        True
    ),
    (
        {'API_BASE_URL': 'https://api.example.com/v1/'},
        True
    ),
    (
        {'@username': 'xyz'},
        False
    ),
    (
        {'USER': 'truenas admin'},
        True
    )
])
@unittest.mock.patch('middlewared.plugins.virt.global.VirtGlobalService.config')
@unittest.mock.patch('middlewared.plugins.virt.instance.VirtInstanceService.validate')
@unittest.mock.patch('middlewared.plugins.virt.instance.incus_call_and_wait')
@unittest.mock.patch('middlewared.plugins.virt.instance.VirtInstanceService.get_account_idmaps')
@unittest.mock.patch('middlewared.plugins.virt.instance.VirtInstanceService.set_account_idmaps')
@unittest.mock.patch('middlewared.plugins.virt.instance.VirtInstanceService.start_impl')
@unittest.mock.patch('middlewared.plugins.virt.instance.incus_call')
@pytest.mark.asyncio
async def test_virt_environment_validation(
    mock_incus_call, mock_start_impl, mock_set_idmaps,
    mock_get_idmaps, mock_incus_call_and_wait, mock_validate,
    mock_config, environment, should_work
):
    middleware = Middleware()
    mock_config.return_value = {
        'pool': 'dozer',
        'storage_pools': ['dozer'],
        'state': 'INITIALIZED'
    }
    mock_validate.return_value = None
    mock_incus_call_and_wait.return_value = None
    mock_get_idmaps.return_value = []
    mock_start_impl.return_value = True
    mock_incus_call.return_value = {'status_code': 400}
    virt_obj = VirtInstanceService(middleware)

    if should_work:
        instance = {
            'name': 'test-vm',
            'image': 'alpine/3.18/default',
            'environment': environment,
            'raw': {'config': {}}
        }
        global_config = {
            'pool': 'dozer',
            'storage_pools': ['dozer'],
            'state': 'INITIALIZED'
        }
        mock_set_idmaps.return_value = instance
        middleware['virt.global.config'] = lambda *args : global_config
        middleware['virt.global.check_initialized'] = lambda *args: True
        middleware['virt.instance.get_instance'] = lambda *args: instance
        middleware['virt.volume.query'] = lambda *args: []

        result = await virt_obj.do_create(12, {
            'name': 'test-vm',
            'image': 'alpine/3.18/default',
            'environment': environment
        })
        assert result is not None
    else:
        with pytest.raises(ValidationErrors):
            await virt_obj.do_create(12, {
                'name': 'test-vm',
                'image': 'alpine/3.18/default',
                'environment': environment
            })
