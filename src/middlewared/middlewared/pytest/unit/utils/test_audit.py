import pytest

from middlewared.auth import (
    ApiKeySessionManagerCredentials,
    UserSessionManagerCredentials,
    TrueNasNodeSessionManagerCredentials
)

from middlewared.utils.audit import audit_username_from_session
from types import SimpleNamespace


USER_SESSION = UserSessionManagerCredentials({'username': 'bob', 'privilege': {'allowlist': []}})
TOKEN_USER_SESSION = SimpleNamespace(root_credentials=USER_SESSION, is_user_session=True, user=USER_SESSION.user)
NODE_SESSION = TrueNasNodeSessionManagerCredentials()


@pytest.mark.parametrize('cred,expected', [
    (None, '.UNAUTHENTICATED'),
    (USER_SESSION, 'bob'),
    (TOKEN_USER_SESSION, 'bob'),
    (NODE_SESSION, '.TRUENAS_NODE')
])
def test_privilege_has_webui_access(cred, expected):
    assert audit_username_from_session(cred) == expected
