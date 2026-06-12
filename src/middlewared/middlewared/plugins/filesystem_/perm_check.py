import errno
import os
import pathlib
from types import MappingProxyType

import truenas_os

from middlewared.service import CallError, Service, private
from middlewared.utils.filesystem.access import get_user_details

_PERM_TOKEN_TO_BIT = MappingProxyType({
    'READ': os.R_OK,
    'WRITE': os.W_OK,
    'EXECUTE': os.X_OK,
})


def _perms_to_mode(perms: list[str]) -> int:
    """Translate a list of ``"READ"`` / ``"WRITE"`` / ``"EXECUTE"`` tokens into
    the bitmask that ``truenas_os.check_path_access`` forwards to faccessat2."""
    mode = 0
    for token in perms:
        bit = _PERM_TOKEN_TO_BIT.get(token)
        if bit is None:
            raise CallError(
                f'{token!r}: invalid perm token; must be one of '
                f'{sorted(_PERM_TOKEN_TO_BIT)}',
                errno.EINVAL,
            )
        mode |= bit
    return mode


def _path_ancestor_components(path: str) -> list[bytes]:
    """Build the ancestor-component byte list expected by truenas_os.check_path_access.

    For ``/mnt/tank/share/file`` this yields ``[b"/mnt", b"/mnt/tank", b"/mnt/tank/share"]``
    — every parent directory between the filesystem root and the leaf, exclusive
    of the leaf itself.
    """
    parts = pathlib.Path(path).parts
    return [('/' + '/'.join(parts[1:i])).encode() for i in range(2, len(parts))]


def _cred_from_user_details(user_details: dict) -> truenas_os.CredEntry:
    return truenas_os.create_cred_entry(
        user_details['id_name'],
        user_details['pw_uid'],
        user_details['pw_gid'],
        user_details['grouplist'],
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
    def can_access_as_user(self, username: str, path: str, perms: list[str]) -> bool:
        """
        Check whether `username` is granted every permission in `perms` on `path`.

        `perms` is a list of ``"READ"`` / ``"WRITE"`` / ``"EXECUTE"`` tokens —
        at least one must be specified.  Returns True iff every requested bit
        is granted by the filesystem (mode bits + native ACLs).
        """
        if not perms:
            raise CallError('At least one of READ/WRITE/EXECUTE must be set', errno.EINVAL)

        mode = _perms_to_mode(perms)

        path_obj = pathlib.Path(path)
        if not path_obj.is_absolute():
            raise CallError('A valid absolute path must be provided', errno.EINVAL)
        elif not path_obj.exists():
            raise CallError(f'{path!r} does not exist', errno.EINVAL)

        try:
            user_details = self.middleware.call_sync('user.get_user_obj', {'username': username, 'get_groups': True})
        except KeyError:
            raise CallError(f'{username!r} user does not exist', errno=errno.ENOENT)

        user_details['id_name'] = user_details['pw_name']
        failures = truenas_os.check_path_access(
            creds=[_cred_from_user_details(user_details)],
            components=[path.encode()],
            mode=mode,
            path_must_exist=True,
        )
        return not failures

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

        components = _path_ancestor_components(path)
        if not components:
            return

        failures = truenas_os.check_path_access(
            creds=[_cred_from_user_details(user_details)],
            components=components,
            path_must_exist=path_must_exist,
        )
        if not failures:
            return

        f = failures[0]
        failing_component = f.failing_component.decode()
        if f.errnum == errno.ENOENT:
            raise CallError(f'{failing_component}: path component does not exist.', errno.ENOENT)

        raise CallError(
            f'Filesystem permissions on path {failing_component} prevent access for '
            f'{id_type.lower()} "{user_details["id_name"]}" to the path {path}. '
            f'This may be fixed by granting the aforementioned {id_type.lower()} '
            f'execute permissions on the path: {failing_component}.', errno.EPERM
        )

    @private
    def check_acl_execute(self, path, acl, uid, gid, path_must_exist=False):
        components = _path_ancestor_components(path)
        if not components:
            return

        creds: list[truenas_os.CredEntry] = []
        id_type_by_name: dict[str, str] = {}
        seen: set[tuple[str, int]] = set()

        for entry in acl:
            if entry['tag'] in ('everyone@', 'OTHER', 'MASK'):
                continue
            if entry.get('type', 'ALLOW') != 'ALLOW':
                continue

            if entry['tag'] == 'GROUP':
                id_type, xid = 'GROUP', entry['id']
            elif entry['tag'] == 'USER':
                id_type, xid = 'USER', entry['id']
            elif entry['tag'] in ('owner@', 'USER_OBJ'):
                id_type, xid = 'USER', uid
            elif entry['tag'] in ('group@', 'GROUP_OBJ'):
                id_type, xid = 'GROUP', gid
            else:
                continue

            key = (id_type, xid)
            if key in seen:
                continue
            seen.add(key)

            details = get_user_details(id_type, xid)
            if details is None:
                continue

            creds.append(_cred_from_user_details(details))
            id_type_by_name[details['id_name']] = id_type

        if not creds:
            return

        failures = truenas_os.check_path_access(
            creds=creds, components=components, path_must_exist=path_must_exist,
        )
        if not failures:
            return

        f = failures[0]
        failing_component = f.failing_component.decode()
        if f.errnum == errno.ENOENT:
            raise CallError(f'{failing_component}: path component does not exist.', errno.ENOENT)

        id_type_lower = id_type_by_name[f.id_name].lower()
        raise CallError(
            f'Filesystem permissions on path {failing_component} prevent access for '
            f'{id_type_lower} "{f.id_name}" to the path {path}. '
            f'This may be fixed by granting the aforementioned {id_type_lower} '
            f'execute permissions on the path: {failing_component}.', errno.EPERM
        )
