import pytest
import types

from middlewared.auth import UserSessionManagerCredentials
from middlewared.utils.privilege import (
    app_credential_full_admin_or_user,
    credential_has_full_admin,
    credential_full_admin_or_user,
    privilege_has_webui_access,
)


@pytest.mark.parametrize('privilege,expected', [
    ({'roles': ['READONLY'], 'allowlist': []}, True),
    ({'roles': ['SHARING_MANAGER'], 'allowlist': []}, True),
    ({'roles': ['FULL_ADMIN'], 'allowlist': []}, True),
    ({'roles': ['SHARING_SMB_READ'], 'allowlist': []}, False),
])
def test_privilege_has_webui_access(privilege, expected):
    assert privilege_has_webui_access(privilege) == expected


@pytest.mark.parametrize('credential,expected', [
    ({'username': 'BOB', 'privilege': {'allowlist': [], 'roles': ['READONLY']}}, False),
    ({'username': 'BOB', 'privilege': {'allowlist': [], 'roles': ['FULL_ADMIN']}}, True),
    ({'username': 'BOB', 'privilege': {'allowlist': [{'method': '*', 'resource': '*'}], 'roles': []}}, True),
])
def test_privilege_has_full_admin(credential,expected):
    user_cred = UserSessionManagerCredentials(credential)
    assert credential_has_full_admin(user_cred) == expected
    assert credential_full_admin_or_user(user_cred, 'canary') == expected
    assert credential_full_admin_or_user(user_cred, 'BOB')

    assert app_credential_full_admin_or_user(types.SimpleNamespace(authenticated_credentials=user_cred), 'canary') == expected
