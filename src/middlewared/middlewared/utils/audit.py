from middlewared.auth import (
    SessionManagerCredentials,
    TokenSessionManagerCredentials,
    TruenasNodeSessionManagerCredentials
)

# Special values start with dot to ensure they cannot collide with local usernames
# created via APIs
API_KEY_PREFIX = '.API_KEY:'
NODE_SESSION = '.TRUENAS_NODE'
UNAUTHENTICATED = '.UNAUTHENTICATED'
UNKNOWN_SESSION = '.UNKNOWN'


def audit_username_from_session(cred: SessionManagerCredentials | None) -> str:
    if cred is None:
        return UNAUTHENTICATED

    # This works for regular user session and tokens formed on them
    if cred.is_user_session:
        return cred.user['username']

    # Track back to root credential if necessary (token session)
    if isinstance(cred, TokenSessionManagerCredentials):
        cred = cred.root_credentials

    elif isinstance(cred, TruenasNodeSessionManagerCredentials):
        return NODE_SESSION

    return UNKNOWN_SESSION
