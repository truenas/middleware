def credential_has_full_admin(credential):
    if credential.is_user_session and 'FULL_ADMIN' in credential.user['privilege']['roles']:
        return True

    return credential.allowlist.full_admin


def credential_username_check(credential, username):
    if credential is None:
        return False

    elif credential_has_full_admin(credential):
        return True

    return credential.user['username'] == username


def app_username_check(app, username):
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

    return credential_username_check(app.authenticated_credentials, username)


def privileges_group_mapping(
    privileges: list,
    group_ids: list,
    groups_key: str,
) -> dict:
    allowlist = []
    roles = set()
    privileges_out = []

    group_ids = set(group_ids)
    for privilege in privileges:
        if set(privilege[groups_key]) & group_ids:
            allowlist.extend(privilege['allowlist'])
            roles |= set(privilege['roles'])
            privileges_out.append(privilege)

    return {
        'allowlist': allowlist,
        'roles': list(roles),
        'privileges': privileges_out
    }
