import pytest

from middlewared.auth import (
    ApiKeySessionManagerCredentials,
    UserSessionManagerCredentials,
    TrueNasNodeSessionManagerCredentials
)

from middlewared.utils.audit import audit_username_from_session
from types import SimpleNamespace


API_KEY = SimpleNamespace(api_key={'id': 1, 'name': 'MY_KEY'})

USER_SESSION = UserSessionManagerCredentials({'username': 'bob', 'privilege': {'allowlist': []}})
API_KEY_SESSION = ApiKeySessionManagerCredentials(API_KEY)
TOKEN_USER_SESSION = SimpleNamespace(root_credentials=USER_SESSION, is_user_session=True, user=USER_SESSION.user)
NODE_SESSION = TrueNasNodeSessionManagerCredentials()


@pytest.mark.parametrize('cred,expected', [
    (None, '.UNAUTHENTICATED'),
    (USER_SESSION, 'bob'),
    (API_KEY_SESSION, '.API_KEY:MY_KEY'),
    (TOKEN_USER_SESSION, 'bob'),
    (NODE_SESSION, '.TRUENAS_NODE')
])
def test_privilege_has_webui_access(cred, expected):
    assert audit_username_from_session(cred) == expected
