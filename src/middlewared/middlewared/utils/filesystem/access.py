import errno
import os
import pathlib
from typing import Any

from middlewared.service_exception import CallError
from middlewared.utils.nss import pwd, grp
from middlewared.utils.user_context import set_user_context

# This should be a sufficiently high UID to never be used explicitly
# We need one for doing access checks based on groups
SYNTHETIC_UID = 2 ** 32 - 2


def check_access(path: str, check_perms: dict[str, bool | None]) -> bool:
    flag = True
    for perm, check_flag in filter(
        lambda v: v[0] is not None, (
            (check_perms['read'], os.R_OK),
            (check_perms['write'], os.W_OK),
            (check_perms['execute'], os.X_OK),
        )
    ):
        perm_check = os.access(path, check_flag)
        flag &= (perm_check if perm else not perm_check)

    return flag


def get_user_details(id_type: str, xid: int) -> dict[str, Any] | None:
    if id_type not in ['USER', 'GROUP']:
        raise CallError(f'{id_type}: invalid ID type. Must be "USER" or "GROUP"')

    if not isinstance(xid, int):
        raise TypeError(f'{type(xid)}: xid must be int.')

    if id_type == 'USER':
        try:
            u = pwd.getpwuid(xid)
            out = {
                'pw_name': u.pw_name,
                'pw_uid': u.pw_uid,
                'pw_gid': u.pw_gid,
                'pw_gecos': u.pw_gecos,
                'pw_dir': u.pw_dir,
                'pw_shell': u.pw_shell,
            }
            out['grouplist'] = os.getgrouplist(u.pw_name, u.pw_gid)
            out['id_name'] = out['pw_name']
            return out
        except KeyError:
            return None

    try:
        g = grp.getgrgid(xid)
        grp_obj = {
            'gr_name': g.gr_name,
            'gr_gid': g.gr_gid,
            'gr_mem': g.gr_mem
        }
    except KeyError:
        return None

    return {
        'pw_name': 'synthetic_user',
        'pw_uid': SYNTHETIC_UID,
        'pw_gid': grp_obj['gr_gid'],
        'pw_gecos': 'synthetic user',
        'pw_dir': '/var/empty',
        'pw_shell': '/usr/bin/zsh',
        'grouplist': [grp_obj['gr_gid']],
        'id_name': grp_obj['gr_name']
    }


def check_acl_execute_impl(path: str, acl: list[dict[str, Any]], uid: int, gid: int, path_must_exist: bool) -> None:
    """
    WARNING: The only way this method should be called is within context of `run_with_user_context`
    """
    parts = pathlib.Path(path).parts

    if not isinstance(uid, int):
        raise TypeError(f'{type(uid)}: uid is not int')

    if not isinstance(gid, int):
        raise TypeError(f'{type(gid)}: gid is not int')

    for entry in acl:
        if entry['tag'] in ('everyone@', 'OTHER', 'MASK'):
            continue

        if entry.get('type', 'ALLOW') != 'ALLOW':
            continue

        # Determine id_type and xid based on the tag
        id_type: str | None = None
        xid: int | None = None

        if entry['tag'] == 'GROUP':
            id_type = 'GROUP'
            xid = entry['id']

        elif entry['tag'] == 'USER':
            id_type = 'USER'
            xid = entry['id']

        elif entry['tag'] in ('owner@', 'USER_OBJ'):
            id_type = 'USER'
            xid = uid

        elif entry['tag'] in ('group@', 'GROUP_OBJ'):
            id_type = 'GROUP'
            xid = gid

        # Skip if we couldn't determine the type or id
        if id_type is None or xid is None:
            continue

        if (user_details := get_user_details(id_type, xid)) is None:
            # Account does not exist on server. Skip validation
            continue

        for idx, part in enumerate(parts):
            if idx < 2:
                continue

            path_to_check = f'/{"/".join(parts[1:idx])}'
            if not os.path.exists(path_to_check):
                if path_must_exist:
                    raise CallError(f'{path_to_check}: path component does not exist.', errno.ENOENT)

                continue

            set_user_context(user_details)
            if not check_access(path_to_check, {'read': None, 'write': None, 'execute': True}):
                raise CallError(
                    f'Filesystem permissions on path {path_to_check} prevent access for '
                    f'{id_type.lower()} "{user_details["id_name"]}" to the path {path}. '
                    f'This may be fixed by granting the aforementioned {id_type.lower()} '
                    f'execute permissions on the path: {path_to_check}.', errno.EPERM
                )
