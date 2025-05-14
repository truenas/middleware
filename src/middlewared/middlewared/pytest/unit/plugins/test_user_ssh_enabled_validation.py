import pytest
from typing import Literal

from middlewared.api.current import UserCreateArgs, UserEntry
from middlewared.plugins.account import UserService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ValidationErrors


@pytest.mark.parametrize('method, twofactor_enabled, twofactor_config, expected_error', [
    (
        'CREATE',
        False,
        {
            'services': {'ssh': False},
            'enabled': False,
        },
        None
    ),
    (
        'CREATE',
        False,
        {
            'services': {'ssh': True},
            'enabled': True,
        },
        '[EINVAL] test_schema.ssh_password_enabled:'
        ' 2FA for this user needs to be explicitly configured before password based SSH access is enabled.'
        ' User will be created with SSH password access disabled and after 2FA has been'
        ' configured for this user, SSH password access can be enabled.'
    ),
    (
        'UPDATE',
        False,
        {
            'services': {'ssh': True},
            'enabled': True,
        },
        '[EINVAL] test_schema.ssh_password_enabled:'
        ' 2FA for this user needs to be explicitly configured before password based SSH access is enabled.'
    ),
    (
        'UPDATE',
        True,
        {
            'services': {'ssh': True},
            'enabled': True,
        },
        None
    ),
    (
        'UPDATE',
        False,
        {
            'services': {'ssh': False},
            'enabled': True,
        },
        None
    ),
    (
        'CREATE',
        False,
        {
            'services': {'ssh': False},
            'enabled': True,
        },
        None
    ),
])
@pytest.mark.asyncio
async def test_use_ssh_enabled_validation(
    method: Literal['CREATE', 'UPDATE'], twofactor_enabled: bool, twofactor_config: dict, expected_error: str
):
    m = Middleware()
    m['datastore.query'] = lambda *arg: []
    m['smb.is_configured'] = lambda *arg: False
    m['auth.twofactor.config'] = lambda *arg: twofactor_config
    m['user.translate_username'] = lambda *args: {'twofactor_auth_configured': twofactor_enabled}
    m['system.security.config'] = lambda *arg: {"enable_fips": False, "enable_gpos_stig": False}

    schema_name = f'user.{method.lower()}'
    if method == 'CREATE':
        data = UserCreateArgs(user_create={
            'username': 'testuser',
            'full_name': 'testuser',
            'group_create': True,
            'home': '/mnt/home/dir',
            'smb': False,
            'password_disabled': True,
            'ssh_password_enabled': True,
        }).model_dump(by_alias=True)
        old_data = None
    else:
        data = {'ssh_password_enabled': True}
        old_data = UserEntry(
            id=0,
            uid=1,
            username='',
            unixhash='unixhash',
            smbhash='smbhash',
            home='/mnt/home/dir',
            full_name='test user',
            builtin=True,
            smb=False,
            group={},
            password_disabled=True,
            id_type_both=False,
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
        ).model_dump(by_alias=True)

    verrors = ValidationErrors()
    if expected_error:
        with pytest.raises(ValidationErrors, match=expected_error) as ve:
            await UserService(m).common_validation(verrors, data, schema_name, [], old_data)
            verrors.check()
    else:
        await UserService(m).common_validation(verrors, data, schema_name, [], old_data)
        verrors.check()
