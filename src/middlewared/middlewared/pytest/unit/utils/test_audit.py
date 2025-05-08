import pytest

from middlewared.auth import (
    UserSessionManagerCredentials,
    TruenasNodeSessionManagerCredentials
)

from middlewared.utils.account.authenticator import UserPamAuthenticator
from middlewared.utils.audit import audit_username_from_session
from middlewared.utils.auth import AA_LEVEL1
from types import SimpleNamespace


USER_SESSION = UserSessionManagerCredentials(
    {'username': 'bob', 'privilege': {'allowlist': []}},
    AA_LEVEL1,
    UserPamAuthenticator()
)
TOKEN_USER_SESSION = SimpleNamespace(root_credentials=USER_SESSION, is_user_session=True, user=USER_SESSION.user)
NODE_SESSION = TruenasNodeSessionManagerCredentials()


@pytest.mark.parametrize('cred,expected', [
    (None, '.UNAUTHENTICATED'),
    (USER_SESSION, 'bob'),
    (TOKEN_USER_SESSION, 'bob'),
    (NODE_SESSION, '.TRUENAS_NODE')
])
def test_privilege_has_webui_access(cred, expected):
    assert audit_username_from_session(cred) == expected
