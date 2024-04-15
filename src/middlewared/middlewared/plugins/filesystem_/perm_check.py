import errno
import grp
import os
import pathlib
import pwd

from middlewared.schema import accepts, Bool, Dict, returns, Str
from middlewared.service import CallError, Service, private

from middlewared.utils.osc import run_with_user_context, set_user_context

# This should be a sufficiently high UID to never be used explicitly
# We need one for doing access checks based on groups
SYNTHETIC_UID = 2 ** 32 -2


def check_access(path: str, check_perms: dict) -> bool:
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


def get_user_details(id_type: str, xid: int) -> dict:
    if id_type not in ['USER', 'GROUP']:
        raise CallError(f'{id_type}: invalid ID type. Must be "USER" or "GROUP"')

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


def check_acl_execute_impl(path: str, acl: list, uid: int, gid: int, path_must_exist: bool):
    """
    WARNING: The only way this method should be called is within context of `run_with_user_context`
    """
    parts = pathlib.Path(path).parts

    for entry in acl:
        if entry['tag'] in ('everyone@', 'OTHER', 'MASK'):
            continue

        if entry.get('type', 'ALLOW') != 'ALLOW':
            continue

        id_info = {'id_type': None, 'xid': entry['id']}

        if entry['tag'] == 'GROUP':
            id_info['id_type'] = 'GROUP'

        elif entry['tag'] == 'USER':
            id_info['id_type'] = 'USER'

        elif entry['tag'] in ('owner@', 'USER_OBJ'):
            id_info['id_type'] = 'USER'
            id_info['xid'] = uid

        elif entry['tag'] in ('group@', 'GROUP_OBJ'):
            id_info['id_type'] = 'USER'
            id_info['xid'] = gid

        if (user_details := get_user_details(**id_info)) is None:
            # Account does not exist on server. Skip validation
            continue

        id_type = id_info['id_type']

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


class FilesystemService(Service):

    @private
    def generate_user_details(self, id_type, xid):
        if id_type not in ['USER', 'GROUP']:
            raise CallError(f'{id_type}: invalid ID type. Must be "USER" or "GROUP"')

        if id_type == 'USER':
            try:
                out = self.middleware.call_sync(
                    'user.get_user_obj',
                    {'uid': xid, 'get_groups': True}
                )
                out['id_name'] = out['pw_name']
                return out
            except KeyError:
                return None

        try:
            grp = self.middleware.call_sync('group.get_group_obj', {'gid': xid})
        except KeyError:
            return None

        # get a UID not currently in use
        tmp_uid = self.middleware.call_sync('user.get_next_uid')

        try:
            res = self.middleware.call_sync(
                'user.get_user_obj',
                {'uid': tmp_uid}
            )
            self.logger.warning(
                '%s: user exists on system but not in TrueNAS configuration. '
                'This may indicate that it was created manually from shell '
                'or there is an unexpected overlap between local and directory '
                'services user accounts', res['pw_name']
            )
            # daemon user probably should not have access to user data
            # so we'll use this for testing
            uid = 1
        except KeyError:
            uid = tmp_uid

        return {
            'pw_name': 'synthetic_user',
            'pw_uid': uid,
            'pw_gid': grp['gr_gid'],
            'pw_gecos': 'synthetic user',
            'pw_dir': '/var/empty',
            'pw_shell': '/usr/bin/zsh',
            'grouplist': [grp['gr_gid']],
            'id_name': grp['gr_name']
        }

    @private
    def check_as_user_imp(self, user_details, path, perms):
        return run_with_user_context(check_access, user_details, [path, perms])

    @accepts(
        Str('username', empty=False),
        Str('path', empty=False),
        Dict(
            'permissions',
            Bool('read', default=None, null=True),
            Bool('write', default=None, null=True),
            Bool('execute', default=None, null=True),
        )
    )
    @returns(Bool())
    def can_access_as_user(self, username, path, perms):
        """
        Check if `username` is able to access `path` with specific `permissions`. At least one of `read/write/execute`
        permission must be specified for checking with each of these defaulting to `null`. `null` for
        `read/write/execute` represents that the permission should not be checked.
        """
        path_obj = pathlib.Path(path)
        if not path_obj.is_absolute():
            raise CallError('A valid absolute path must be provided', errno.EINVAL)
        elif not path_obj.exists():
            raise CallError(f'{path!r} does not exist', errno.EINVAL)

        if all(v is None for v in perms.values()):
            raise CallError('At least one of read/write/execute flags must be set', errno.EINVAL)

        try:
            user_details = self.middleware.call_sync('user.get_user_obj', {'username': username, 'get_groups': True})
        except KeyError:
            raise CallError(f'{username!r} user does not exist', errno=errno.ENOENT)

        return self.check_as_user_impl(user_details, path, perms)

    @private
    def check_path_execute(self, path, id_type, xid, path_must_exist):
        user_details = self.generate_user_details(id_type, xid)
        if user_details is None:
            # User or group does not exist on server.
            # This can happen for a variety of reasons that are potentially
            # acceptable (or better than alternative of changing permissions).
            # Hence, skip validation.
            self.logger.trace('%s %d does not exist. Skipping validation',
                              id_type.lower(), xid)
            return

        parts = pathlib.Path(path).parts
        for idx, part in enumerate(parts):
            if idx < 2:
                continue

            path_to_check = f'/{"/".join(parts[1:idx])}'
            if not os.path.exists(path_to_check):
                if path_must_exist:
                    raise CallError(f'{path_to_check}: path component does not exist.', errno.ENOENT)

                continue

            ok = self.check_as_user_impl(user_details, path_to_check, {'read': None, 'write': None, 'execute': True})
            if not ok:
                raise CallError(
                    f'Filesystem permissions on path {path_to_check} prevent access for '
                    f'{id_type.lower()} "{user_details["id_name"]}" to the path {path}. '
                    f'This may be fixed by granting the aforementioned {id_type.lower()} '
                    f'execute permissions on the path: {path_to_check}.', errno.EPERM
                )

    @private
    def check_acl_execute(self, path, acl, uid, gid, path_must_exist=False):
        run_with_user_context(check_acl_execute_impl, {
            'pw_uid': 0, 'pw_gid': 0, 'pw_dir': '/var/empty', 'pw_name': 'root', 'grouplist': [0, 544]
        }, [path, acl, uid, gid, path_must_exist])
