import pytest

from middlewared.plugins.account import UserService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ValidationErrors


@pytest.mark.parametrize('data,old_data,twofactor_enabled,twofactor_config,expected_error', [
    (
        {
            'ssh_password_enabled': True
        },
        None,
        False,
        {
            'services': {
                'ssh': False
            },
            'enabled': False,
        },
        ''
    ),
    (
        {
            'ssh_password_enabled': True
        },
        None,
        False,
        {
            'services': {
                'ssh': True
            },
            'enabled': True,
        },
        '[EINVAL] test_schema.ssh_password_enabled:'
        ' 2FA for this user needs to be explicitly configured before password based SSH access is enabled.'
        ' User will be created with SSH password access disabled and after 2FA has been'
        ' configured for this user, SSH password access can be enabled.'
    ),
    (
        {
            'ssh_password_enabled': True
        },
        {},
        False,
        {
            'services': {
                'ssh': True
            },
            'enabled': True,
        },
        '[EINVAL] test_schema.ssh_password_enabled:'
        ' 2FA for this user needs to be explicitly configured before password based SSH access is enabled.'
    ),
    (
        {
            'ssh_password_enabled': True
        },
        {},
        True,
        {
            'services': {
                'ssh': True
            },
            'enabled': True,
        },
        ''
    ),
    (
        {
            'ssh_password_enabled': True
        },
        {},
        False,
        {
            'services': {
                'ssh': False
            },
            'enabled': True,
        },
        ''
    ),
    (
        {
            'ssh_password_enabled': True
        },
        None,
        False,
        {
            'services': {
                'ssh': False
            },
            'enabled': True,
        },
        ''
    ),

])
@pytest.mark.asyncio
async def test_use_ssh_enabled_validation(data, old_data, twofactor_enabled, twofactor_config, expected_error):
    m = Middleware()
    m['datastore.query'] = lambda *arg: []
    m['smb.is_configured'] = lambda *arg: False
    m['auth.twofactor.config'] = lambda *arg: twofactor_config
    m['user.translate_username'] = lambda *args: {'twofactor_auth_configured': twofactor_enabled}
    data['smb'] = False
    data.update(
        {
            'smb': False,
            'password_disabled': True
        }
    )
    if old_data is not None:
        old_data.update(
            {
                'username': '',
                'id': 0
            }
        )
    verrors = ValidationErrors()
    if expected_error:
        with pytest.raises(ValidationErrors) as ve:
            await UserService(m).common_validation(verrors, data, 'test_schema', [], old_data,)
            verrors.check()
        assert str(ve.value.errors[0]) == expected_error
    else:
        await UserService(m).common_validation(verrors, data, 'test_schema', [], old_data, )
        assert list(verrors) == []
