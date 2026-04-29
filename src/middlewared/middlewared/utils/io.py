# NOTE: tests are provided in tests/unit/test_write_if_changed.py
# Any updates to this file should have corresponding updates to tests

import enum
import os
import stat

import truenas_os
from truenas_os_pyutils.io import atomic_replace

ID_MAX = 2 ** 32 - 2


class FileChanges(enum.IntFlag):
    CONTENTS = enum.auto()
    UID = enum.auto()
    GID = enum.auto()
    PERMS = enum.auto()

    @staticmethod
    def dump(mask: int) -> list[str]:
        if unmapped := mask & ~int(FileChanges.CONTENTS | FileChanges.UID | FileChanges.GID | FileChanges.PERMS):
            raise ValueError(f'{unmapped}: unsupported flags in mask')

        return [
            change.name for change in FileChanges if mask & change and change.name is not None
        ]


class UnexpectedFileChange(Exception):
    def __init__(self, path: str, changes: int) -> None:
        self.changes = changes
        self.path = path
        self.changes_str = ', '.join(FileChanges.dump(self.changes))
        super().__init__(path, changes)

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
                     tmpdir: str | None = None, raise_error: bool = False) -> int:
    """
    Commit changes to a configuration file.
    `path` - absolute path to configuration file.

    `data` - expected file contents. May be bytes or string

    `uid` - expected numeric UID for file

    `gid` - expected numeric GID for file

    `perms` - numeric permissions that file should have

    `tmpdir` - optional directory for temporary file creation during atomic replace.
    If None, uses the directory containing `path`. Must be on the same filesystem as `path`.

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

    if not os.path.isabs(path):
        raise ValueError(f'{path}: path must be absolute')

    temp_path = tmpdir if tmpdir is not None else os.path.dirname(path)

    changes = 0

    try:
        with open(truenas_os.openat2(path, os.O_RDONLY, resolve=truenas_os.RESOLVE_NO_SYMLINKS), 'rb+') as f:
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
        atomic_replace(
            temp_path=temp_path,
            target_file=path,
            perms=perms,
            data=data,
            uid=uid,
            gid=gid
        )
    elif changes != 0 and raise_error:
        raise UnexpectedFileChange(path, changes)

    return changes
