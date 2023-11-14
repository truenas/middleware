def credential_has_full_admin(credential):
    if credential.is_user_session and 'FULL_ADMIN' in credential.user['privilege']['roles']:
       return True

    return credential.allowlist.full_admin


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
