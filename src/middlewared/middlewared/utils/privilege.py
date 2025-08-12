from typing import TYPE_CHECKING

from middlewared.auth import TruenasNodeSessionManagerCredentials
from middlewared.role import ROLES
if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.auth import SessionManagerCredentials


def privilege_has_webui_access(privilege: dict) -> bool:
    """
    This method determines whether the specified privilege is sufficient
    to grant WebUI access. Current check is whether any of the roles for
    the privilege entry are not builtin, where "builtin" means an
    internal role that is used for defining access to particular methods
    (as opposed to non-builtin ones that were developed explicitly for
    assignment by administrators).

    The actual check performed here may change at a future time if we
    decide to add explicit `webui_access` flag to privilege.

    Returns True if privilege grants webui access and False if it does not.
    """
    return any(ROLES[role].builtin is False for role in privilege['roles'])


def credential_has_full_admin(credential: 'SessionManagerCredentials') -> bool:
    if credential.is_user_session and 'FULL_ADMIN' in credential.user['privilege']['roles']:
        return True

    if isinstance(credential, TruenasNodeSessionManagerCredentials):
        return True

    if credential.allowlist is None:
        return False

    return credential.allowlist.full_admin


def credential_full_admin_or_user(
    credential: 'SessionManagerCredentials | None',
    username: str
) -> bool:
    if credential is None:
        return False

    elif credential_has_full_admin(credential):
        return True

    return credential.user['username'] == username


def app_credential_full_admin_or_user(
    app: 'App',
    username: str
) -> bool:
    """
    Privilege check for whether credential has full admin privileges
    or matches the specified username

    Returns True on success and False on failure

    Success:
    * app is None - internal middleware call
    * credential is a user session and has FULL_ADMIN role
    * credential has a wildcard entry in allow list
    * credential username matches `username` passed into this method
    """
    if app is None:
        return True

    return credential_full_admin_or_user(app.authenticated_credentials, username)


def privileges_group_mapping(
    privileges: list[dict],
    group_ids: list,
    groups_key: str,
) -> dict:
    roles = set()
    privileges_out = []

    group_ids_ = set(group_ids)
    for privilege in privileges:
        if set(privilege[groups_key]) & group_ids_:
            roles |= set(privilege['roles'])
            privileges_out.append(privilege)

    return {
        'roles': list(roles),
        'privileges': privileges_out
    }


def credential_is_limited_to_own_jobs(credential: 'SessionManagerCredentials | None') -> bool:
    if credential is None or not credential.is_user_session:
        return False

    return not credential_has_full_admin(credential)


def credential_is_root_or_equivalent(credential: 'SessionManagerCredentials | None') -> bool:
    if credential is None or not credential.is_user_session:
        return False

    # SYS_ADMIN is set when user UID is 0 (root) or 950 (truenas_admin).
    return 'SYS_ADMIN' in credential.user['account_attributes']
