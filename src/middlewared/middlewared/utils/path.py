# -*- coding=utf-8 -*-
from contextlib import contextmanager
import errno
import enum
import fcntl
import logging
import os
from pathlib import Path
import stat
from typing import Iterable, TYPE_CHECKING

from middlewared.utils.filesystem.constants import ZFSCTL
if TYPE_CHECKING:
    from middlewared.service_exception import ValidationErrors


__all__ = ["pathref_open", "pathref_reopen", "is_child", "is_child_realpath", "path_location"]

logger = logging.getLogger(__name__)

EXTERNAL_PATH = 'EXTERNAL'
EXTERNAL_PATH_PREFIX = 'EXTERNAL:'


class FSLocation(enum.Enum):
    EXTERNAL = enum.auto()
    LOCAL = enum.auto()


def path_location(path: str) -> FSLocation:
    if path == EXTERNAL_PATH or path.startswith(EXTERNAL_PATH_PREFIX):
        return FSLocation.EXTERNAL

    return FSLocation.LOCAL


def check_path_resides_within_volume_sync(
    verrors: 'ValidationErrors', schema_name: str, path: str, vol_names: Iterable[str], must_be_dir: bool = False
) -> None:
    """This provides basic validation of whether a given `path` is allowed to be exposed to end-users.

    It checks the following:
    * `path` is within /mnt
    * `path` is located within one of the specified `vol_names`
    * `path` is not explicitly a `.zfs` or `.zfs/snapshot` directory

    :param verrors:     `ValidationErrors` created by calling function.
    :param schema_name: Schema name to use in validation error message.
    :param path:        Path to validate.
    :param vol_names:   List of expected pool names.
    :param must_be_dir: Optional check for directory.

    """
    if path_location(path).name == 'EXTERNAL':
        # There are some fields where we allow external paths
        verrors.add(schema_name, "Path is external to TrueNAS.")
        return

    try:
        inode = os.stat(path).st_ino
    except FileNotFoundError:
        inode = None

    rp = Path(os.path.realpath(path))

    if must_be_dir and not rp.is_dir():
        verrors.add(schema_name, "The path must be a directory")

    vol_paths = [os.path.join("/mnt", vol_name) for vol_name in vol_names]
    if not path.startswith("/mnt/") or not any(
        os.path.commonpath([parent]) == os.path.commonpath([parent, rp]) for parent in vol_paths
    ):
        verrors.add(schema_name, "The path must reside within a pool mount point")

    if inode in (ZFSCTL.INO_ROOT.value, ZFSCTL.INO_SNAPDIR.value):
        verrors.add(
            schema_name,
            "The ZFS control directory (.zfs) and snapshot directory (.zfs/snapshot) "
            "are not permitted paths. If a snapshot within this directory must "
            "be accessed through the path-based API, then it should be called "
            "directly, e.g. '/mnt/dozer/.zfs/snapshot/mysnap'."
        )


def pathref_reopen(fd_in: int, flags: int, *, close_fd: bool = False, mode: int = 0o777) -> int:
    # use procfs to reopen a file with new flags
    if fcntl.fcntl(fd_in, fcntl.F_GETFL) & os.O_PATH == 0:
        raise ValueError('Not an O_PATH open')

    pathref = f'/proc/self/fd/{fd_in}'
    fd_out = os.open(pathref, flags, mode)
    if close_fd:
        os.close(fd_in)

    return fd_out


@contextmanager
def pathref_open(
    path: str,
    *,
    dir_fd: int | None = None,
    additional_flags: int = 0,
    expected_mode: int | None = None,
    force: bool = False,
    mkdir: bool = False,
):
    """Get O_PATH open for specified `path`.

    :param dir_fd: Fileno for open of to use as dir_fd for open of path.

    :param expected_mode: Expected permissions on open of `path`. If the `force` kwarg is also set then the file's
        permissions will be changed to the specified value. Otherwise ValueError will be raised on permissions mismatch.

    :param force: If path is a symbolic link, then the symlink will be removed and replaced with a directory. In case of
        mismatch between expected_mode and stat() output, chmod(2) will be called.

    :param mkdir: If `path` does not exist, then it will be created.

    """
    flags = os.O_PATH | os.O_NOFOLLOW | additional_flags
    fd = -1

    try:
        fd = os.open(path, flags, dir_fd=dir_fd)
    except FileNotFoundError:
        if not mkdir:
            raise

        os.mkdir(path, expected_mode or 0o755, dir_fd=dir_fd)
        fd = os.open(path, flags, dir_fd=dir_fd)
    except OSError as e:
        # open will fail with ELOOP if last component is symlink
        # due to O_NOFOLLOW
        if e.errno != errno.ELOOP or not force:
            raise

        os.unlink(path, dir_fd=dir_fd)
        os.mkdir(path, expected_mode or 0o755, dir_fd=dir_fd)
        fd = os.open(path, flags, dir_fd=dir_fd)

    st = os.fstat(fd)

    if not stat.S_ISDIR(st.st_mode):
        os.close(fd)
        raise NotADirectoryError(path)

    if expected_mode and stat.S_IMODE(st.st_mode) != expected_mode:
        if not force:
            raise ValueError(
                f'{stat.S_IMODE(st.st_mode)} does not match expected mode: '
                f'{expected_mode}, and "force" was not specified.'
            )

        try:
            tmp_fd = pathref_reopen(fd, os.O_DIRECTORY)
            try:
                os.fchmod(tmp_fd, expected_mode)
            finally:
                os.close(tmp_fd)
        except Exception:
            os.close(fd)
            raise

    try:
        yield fd
    finally:
        os.close(fd)


def is_child_realpath(child: str, parent: str) -> bool:
    """
    This method blocks, but uses realpath to determine
    whether the specified path is a child of another.
    Python realpath checks each path component for whether
    it's a symlink, but may not do so in a race-free way.

    For internal purposes though, this is sufficient for
    how we use it (primarily to determine whether a share
    path is locked, etc).
    """
    c = Path(child)
    p = Path(parent)

    if c == p:
        return True

    return c.resolve().is_relative_to(p.resolve())


def is_child(child: str, parent: str) -> bool:
    """
    This method is asyncio safe, but should not be used
    to check whether one local path is a child of another.

    An example where it may be useful is determining whether
    a dataset name is a child of another.
    """
    if os.path.isabs(child) or os.path.isabs(parent):
        raise ValueError(f'Symlink-unsafe method called with absolute path(s): {child}, {parent}')

    rel = os.path.relpath(child, parent)
    return rel == "." or not rel.startswith("..")
