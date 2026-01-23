# NOTE: tests are provided in src/middlewared/middlewared/pytest/unit/utils/test_write_if_changed.py
# Any updates to this file should have corresponding updates to tests

import fcntl
import os
import enum
import stat
from tempfile import NamedTemporaryFile


ID_MAX = 2 ** 32 - 2


class FileChanges(enum.IntFlag):
    CONTENTS = enum.auto()
    UID = enum.auto()
    GID = enum.auto()
    PERMS = enum.auto()

    def dump(mask: int) -> list[str]:
        if unmapped := mask & ~int(FileChanges.CONTENTS | FileChanges.UID | FileChanges.GID | FileChanges.PERMS):
            raise ValueError(f'{unmapped}: unsupported flags in mask')

        return [
            change.name for change in FileChanges if mask & change
        ]


class UnexpectedFileChange(Exception):
    def __init__(self, path: str, changes: int) -> None:
        self.changes = changes
        self.path = path
        self.changes_str = ', '.join(FileChanges.dump(self.changes))

    def __str__(self) -> str:
        return f'{self.path}: unexpected change in the following file attributes: {self.changes_str}'


def get_io_uring_enabled() -> bool:
    with open('/proc/sys/kernel/io_uring_disabled', 'r') as f:
        disabled_val = int(f.read().strip())

    return disabled_val == 0


def set_io_uring_enabled(enabled_val: bool) -> bool:
    with open('/proc/sys/kernel/io_uring_disabled', 'w') as f:
        f.write('0' if enabled_val else '2')
        f.flush()

    return get_io_uring_enabled()


def write_if_changed(path: str, data: str | bytes, uid: int = 0, gid: int = 0, perms: int = 0o755,
                     dirfd: int | None = None, raise_error: bool = False) -> int:
    """
    Commit changes to a configuration file.
    `path` - path to configuration file. May be relative to a specified `dirfd`

    `data` - expected file contents. May be bytes or string

    `uid` - expected numeric UID for file

    `gid` - expected numeric GID for file

    `perms` - numeric permissions that file should have

    `dirfd` - optional open file descriptor (may be O_PATH or O_DIRECTORY) if `path` is
    relative.

    `raise_error` - raise an UnexpectedFileChange exception if file ownership or
    permissions have unexpectedly changed.
    """

    if isinstance(data, str):
        data = data.encode()

    if not isinstance(perms, int):
        raise ValueError('perms must be an integer')

    if perms & ~(stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError(f'{perms}: invalid mode. Supported bits are RWX for UGO.')

    for xid in ((uid, 'uid'), (gid, 'gid')):
        value, name = xid
        if not isinstance(value, int):
            raise ValueError(f'{name} must be an integer')

        if value < 0 or value > ID_MAX:
            raise ValueError(f'{name} must be between 0 and {ID_MAX}')

    if dirfd is not None:
        if not isinstance(dirfd, int):
            raise ValueError('dirfd must be a valid file descriptor')

        if not os.path.exists(f'/proc/self/fd/{dirfd}'):
            raise ValueError(f'{dirfd}: file descriptor not found')

        if os.path.isabs(path):
            raise ValueError(f'{path}: absolute paths may not be used with a `dirfd`')

        if fcntl.fcntl(dirfd, fcntl.F_GETFL) & (os.O_DIRECTORY | os.O_PATH) == 0:
            raise ValueError('dirfd must be opened via O_DIRECTORY or O_PATH')

        # tempfile API does not permit using a file descriptor
        # so we'll get the underlying directory name from procfs
        parent_dir = os.readlink(f'/proc/self/fd/{dirfd}')
    else:
        if not os.path.isabs(path):
            raise ValueError(f'{path}: relative paths may not be used without a `dirfd`')

        parent_dir = os.path.dirname(path)

    changes = 0

    try:
        with open(os.open(path, os.O_RDONLY, dir_fd=dirfd), 'rb+') as f:
            current = f.read()
            if current != data:
                changes |= FileChanges.CONTENTS

            # The following cannot be skipped if we're changing file contents
            # because we want accurate list of what has changed in file.

            st = os.fstat(f.fileno())
            if stat.S_IMODE(st.st_mode) != perms:
                changes |= FileChanges.PERMS

            if st.st_uid != uid:
                changes |= FileChanges.UID

            if st.st_gid != gid:
                changes |= FileChanges.GID

            if changes & (FileChanges.UID | FileChanges.GID):
                os.fchown(f.fileno(), uid, gid)

            if changes & FileChanges.PERMS:
                os.fchmod(f.fileno(), perms)

    except FileNotFoundError:
        # Do not specify we're changing permissions on file
        # because we're creating it new
        changes = FileChanges.CONTENTS

    if changes & FileChanges.CONTENTS:
        with NamedTemporaryFile(mode='wb+', dir=parent_dir, delete=False) as tmp:
            tmp.file.write(data)
            tmp.file.flush()
            os.fsync(tmp.file.fileno())
            os.fchmod(tmp.file.fileno(), perms)
            os.fchown(tmp.file.fileno(), uid, gid)
            source_path = tmp.name

        if dirfd is not None:
            os.rename(source_path, path, src_dir_fd=dirfd, dst_dir_fd=dirfd)

        else:
            os.rename(source_path, path)

    elif changes != 0 and raise_error:
        raise UnexpectedFileChange(path, changes)

    return changes
