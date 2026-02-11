# NOTE: tests are provided in src/middlewared/middlewared/pytest/unit/utils/test_write_if_changed.py
# Any updates to this file should have corresponding updates to tests

from contextlib import contextmanager
import fcntl
import os
import enum
import stat
import truenas_os
from tempfile import TemporaryDirectory


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


def atomic_replace(
    *,
    temp_path: str,
    target_file: str,
    data: bytes,
    uid: int = 0,
    gid: int = 0,
    perms: int = 0o755
) -> None:
    """Atomically replace a file's contents with symlink race protection.

    Uses openat2 with RESOLVE_NO_SYMLINKS and renameat2 with AT_RENAME_EXCHANGE
    to safely replace a file's contents without risk of:
    - Partially written files visible to readers
    - Symlink race conditions (TOCTOU attacks)
    - Data loss if write operation fails

    The function creates a temporary file in a secure temporary directory,
    writes the data with proper ownership and permissions, syncs to disk,
    then atomically exchanges it with the target file.

    Args:
        temp_path: Directory for temporary file creation. Must be on the same
                   filesystem as target_file and must not contain symlinks in path.
        target_file: Absolute path to the file to replace. Path must not contain
                     symlinks.
        data: Binary data to write to the file.
        uid: User ID for file ownership (default: 0/root).
        gid: Group ID for file ownership (default: 0/root).
        perms: File permissions as octal integer (default: 0o755).

    Raises:
        OSError: If openat2/renameat2 operations fail.
        ValueError: If paths contain symlinks (RESOLVE_NO_SYMLINKS).

    Note:
        - temp_path and target_file must be on the same filesystem for rename to work
        - All file descriptors are properly closed even on error
        - If target_file doesn't exist, uses regular rename instead of exchange
    """
    with atomic_write(target_file, "wb", tmppath=temp_path, uid=uid, gid=gid, perms=perms) as f:
        f.write(data)


@contextmanager
def atomic_write(target: str, mode: str = "w", *, tmppath: str | None = None,
                 uid: int = 0, gid: int = 0, perms: int = 0o755):
    """Context manager for atomic file writes with symlink race protection.

    Yields a file-like object for writing. On successful context manager exit,
    atomically replaces the target file using renameat2 with proper synchronization.
    Uses openat2 with RESOLVE_NO_SYMLINKS and renameat2 with AT_RENAME_EXCHANGE
    to safely replace a file's contents without risk of:
    - Partially written files visible to readers
    - Symlink race conditions (TOCTOU attacks)
    - Data loss if write operation fails

    Args:
        target: Absolute path to the file to write/replace. Path must not contain
                symlinks.
        mode: File open mode, either "w" (text) or "wb" (binary). Defaults to "w".
        tmppath: Directory for temporary file creation. If None, uses dirname(target).
                 Must be on same filesystem as target and must not contain symlinks.
        uid: User ID for file ownership (default: 0/root).
        gid: Group ID for file ownership (default: 0/root).
        perms: File permissions as octal integer (default: 0o755).

    Yields:
        File-like object for writing

    Raises:
        OSError: If openat2/renameat2 operations fail.
        ValueError: If paths contain symlinks (RESOLVE_NO_SYMLINKS) or mode is invalid.

    Note:
        - tmppath and target must be on the same filesystem for rename to work
        - If target doesn't exist, uses regular rename instead of exchange
        - File is only replaced if the context manager exits successfully
        - All file descriptors are properly closed even on error

    Example:
        with atomic_write('/etc/config.conf') as f:
            f.write("config data")
        # File is atomically replaced here
    """
    if mode not in ("w", "wb"):
        raise ValueError(f'{mode}: invalid mode. Only "w" and "wb" are supported.')

    if tmppath is None:
        tmppath = os.path.dirname(target)

    with TemporaryDirectory(dir=tmppath) as tmpdir:
        # Get directory file descriptors with symlink protection
        dst_dirpath = os.path.dirname(target)
        target_filename = os.path.basename(target)

        dst_dirfd = truenas_os.openat2(dst_dirpath, os.O_DIRECTORY, resolve=truenas_os.RESOLVE_NO_SYMLINKS)

        try:
            src_dirfd = truenas_os.openat2(tmpdir, os.O_DIRECTORY, resolve=truenas_os.RESOLVE_NO_SYMLINKS)
        except Exception:
            os.close(dst_dirfd)
            raise

        # Check if target exists to determine rename strategy
        try:
            os.lstat(target_filename, dir_fd=dst_dirfd)
            rename_flags = truenas_os.AT_RENAME_EXCHANGE
        except FileNotFoundError:
            rename_flags = 0
        except Exception:
            os.close(dst_dirfd)
            os.close(src_dirfd)
            raise

        # Create temporary file
        try:
            temp_fd = os.open(target_filename, os.O_RDWR | os.O_CREAT, mode=perms, dir_fd=src_dirfd)
        except Exception:
            os.close(dst_dirfd)
            os.close(src_dirfd)
            raise

        # Set ownership and permissions
        try:
            os.fchown(temp_fd, uid, gid)
            # Explicitly set permissions to ensure they're correct regardless of umask
            os.fchmod(temp_fd, perms)
        except Exception:
            os.close(dst_dirfd)
            os.close(src_dirfd)
            raise

        # Yield file handle for writing
        try:
            with open(temp_fd, mode) as f:
                yield f
                # Ensure data is written to disk
                f.flush()
                os.fsync(temp_fd)
        except Exception:
            os.close(dst_dirfd)
            os.close(src_dirfd)
            raise

        # Perform atomic rename
        try:
            truenas_os.renameat2(
                src=target_filename,
                dst=target_filename,
                src_dir_fd=src_dirfd,
                dst_dir_fd=dst_dirfd,
                flags=rename_flags
            )
        finally:
            os.close(dst_dirfd)
            os.close(src_dirfd)


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
        # Construct absolute path for atomic_replace
        absolute_path = os.path.join(parent_dir, path)
    else:
        if not os.path.isabs(path):
            raise ValueError(f'{path}: relative paths may not be used without a `dirfd`')

        parent_dir = os.path.dirname(path)
        absolute_path = path

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
        atomic_replace(
            temp_path=parent_dir,
            target_file=absolute_path,
            perms=perms,
            data=data,
            uid=uid,
            gid=gid
        )
    elif changes != 0 and raise_error:
        raise UnexpectedFileChange(path, changes)

    return changes
