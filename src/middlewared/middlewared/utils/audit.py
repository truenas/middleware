from middlewared.auth import (
    SessionManagerCredentials,
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
        return cred.user['username']  # type: ignore[no-any-return, attr-defined]

    if isinstance(cred, TruenasNodeSessionManagerCredentials):
        return NODE_SESSION

    return UNKNOWN_SESSION
