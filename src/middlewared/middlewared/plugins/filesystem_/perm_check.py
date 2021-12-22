import errno
import os
import pathlib

from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection

from middlewared.schema import accepts, Bool, Dict, returns, Str
from middlewared.service import CallError, Service

from middlewared.utils.osc import set_user_context


def check_access(user: str, path: str, check_perms: dict, pipe: Connection) -> None:
    set_user_context(user)

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

    pipe.send(flag)


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

        parent_con, child_con = Pipe()
        try:
            proc = Process(target=check_access, args=(username, path, perms, child_con), daemon=True)
            proc.start()
            can_access = parent_con.recv()
            proc.join()
        finally:
            child_con.close()
            parent_con.close()

        return can_access
