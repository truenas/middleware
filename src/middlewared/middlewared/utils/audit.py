from middlewared.auth import (
    ApiKeySessionManagerCredentials,
    TokenSessionManagerCredentials,
    TrueNasNodeSessionManagerCredentials
)

# Special values start with dot to ensure they cannot collide with local usernames
# created via APIs
API_KEY_PREFIX = '.API_KEY:'
NODE_SESSION = '.TRUENAS_NODE'
UNAUTHENTICATED = '.UNAUTHENTICATED'
UNKNOWN_SESSION = '.UNKNOWN'


def audit_username_from_session(cred) -> str:
    if cred is None:
        return UNAUTHENTICATED

    # This works for regular user session and tokens formed on them
    if cred.is_user_session:
        return cred.user['username']

    # Track back to root credential if necessary (token session)
    if isinstance(cred, TokenSessionManagerCredentials):
        cred = cred.root_credentials

    if isinstance(cred, ApiKeySessionManagerCredentials):
        return f'{API_KEY_PREFIX}{cred.api_key.api_key["name"]}'

    elif isinstance(cred, TrueNasNodeSessionManagerCredentials):
        return NODE_SESSION

    return UNKNOWN_SESSION
