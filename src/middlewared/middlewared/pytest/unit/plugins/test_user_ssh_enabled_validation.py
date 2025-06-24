import pytest
from typing import Literal

from middlewared.api.current import UserCreateArgs, UserEntry
from middlewared.plugins.account import UserService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ValidationErrors


@pytest.mark.parametrize('method, twofactor_enabled, twofactor_config, expected_error', [
    (
        'create',
        False,
        {
            'services': {'ssh': False},
            'enabled': False,
        },
        None
    ),
    (
        'create',
        False,
        {
            'services': {'ssh': False},
            'enabled': True,
        },
        None
    ),
    (
        'create',
        False,
        {
            'services': {'ssh': True},
            'enabled': True,
        },
        '2FA for this user needs to be explicitly configured before password based SSH access is enabled.'
        ' User will be created with SSH password access disabled and after 2FA has been'
        ' configured for this user, SSH password access can be enabled.'
    ),
    (
        'update',
        False,
        {
            'services': {'ssh': False},
            'enabled': True,
        },
        None
    ),
    (
        'update',
        False,
        {
            'services': {'ssh': True},
            'enabled': True,
        },
        '2FA for this user needs to be explicitly configured before password based SSH access is enabled.'
    ),
    (
        'update',
        True,
        {
            'services': {'ssh': True},
            'enabled': True,
        },
        None
    ),
])
@pytest.mark.asyncio
async def test_use_ssh_enabled_validation(
    method: Literal['create', 'update'], twofactor_enabled: bool, twofactor_config: dict, expected_error: str
):
    m = Middleware()
    m['datastore.query'] = lambda name, *args: [{'vol_name': 'home'}] if name == 'storage.volume' else []
    m['smb.is_configured'] = lambda *args: False
    m['auth.twofactor.config'] = lambda *args: twofactor_config
    m['user.shell_choices'] = lambda *args: {'/usr/bin/zsh': 'zsh'}
    m['user.translate_username'] = lambda *args: {'twofactor_auth_configured': twofactor_enabled}
    m['system.security.config'] = lambda *args: {'enable_fips': False, 'enable_gpos_stig': False}
    user_service = UserService(m)
    user_service.validate_homedir_path = lambda *args: True

    schema_name = f'user.{method}'
    if method == 'create':
        data = UserCreateArgs(user_create={
            'username': 'testuser',
            'full_name': 'testuser',
            'group_create': True,
            'home': '/mnt/home/dir',
            'smb': False,
            'password_disabled': True,
            'ssh_password_enabled': True,
        }).model_dump(by_alias=True, context={'expose_secrets': True})['user_create']
        old_data = None
    else:
        data = {'ssh_password_enabled': True}
        old_data = UserEntry(
            id=0,
            uid=1,
            username='testuser',
            unixhash='unixhash',
            smbhash='smbhash',
            home='/mnt/home/dir',
            full_name='testuser',
            builtin=True,
            smb=False,
            group={},
            password_disabled=True,
            local=True,
            immutable=False,
            twofactor_auth_configured=twofactor_enabled,
            sid=None,
            last_password_change=None,
            password_age=None,
            password_history=None,
            password_change_required=False,
            roles=[],
            api_keys=[],
        ).model_dump(by_alias=True, context={'expose_secrets': True})

    verrors = ValidationErrors()
    if expected_error:
        with pytest.raises(ValidationErrors, match=expected_error):
            await user_service.common_validation(verrors, data, schema_name, [], old_data)
            verrors.check()
    else:
        await user_service.common_validation(verrors, data, schema_name, [], old_data)
        verrors.check()
