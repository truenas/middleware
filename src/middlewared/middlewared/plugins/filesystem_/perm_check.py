import errno
import pathlib

from middlewared.schema import accepts, Bool, Dict, returns, Str
from middlewared.service import CallError, Service

from middlewared.utils.osc import run_command_with_user_context


class FilesystemService(Service):

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

        check = []
        for flag, flag_set in filter(
            lambda v: v[1] is not None, (
                ('-r', perms['read']),
                ('-w', perms['write']),
                ('-x', perms['execute']),
            )
        ):
            check.append(' '.join(filter(bool, ['[', '!' if flag_set is False else '', flag, path, ']'])))

        cp = run_command_with_user_context(' && '.join(check), username, lambda x: x)
        return True if cp.returncode == 0 else False
