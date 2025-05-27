# -*- coding=utf-8 -*-
import errno
import enum
import fcntl
import logging
import os
import stat

from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ["pathref_open", "pathref_reopen", "is_child", "is_child_realpath", "path_location"]

EXTERNAL_PATH = 'EXTERNAL'
EXTERNAL_PATH_PREFIX = 'EXTERNAL:'


class FSLocation(enum.Enum):
    EXTERNAL = enum.auto()
    LOCAL = enum.auto()


def path_location(path):
    if path == EXTERNAL_PATH or path.startswith(EXTERNAL_PATH_PREFIX):
        return FSLocation.EXTERNAL

    return FSLocation.LOCAL


def pathref_reopen(fd_in: int, flags: int, **kwargs) -> int:
    # use procfs to reopen a file with new flags
    if fcntl.fcntl(fd_in, fcntl.F_GETFL) & os.O_PATH == 0:
        raise ValueError('Not an O_PATH open')

    close = kwargs.get('close_fd', False)
    mode = kwargs.get('mode', 0o777)

    pathref = f'/proc/self/fd/{fd_in}'
    fd_out = os.open(pathref, flags, mode)
    if close:
        os.close(fd_in)

    return fd_out


@contextmanager
def pathref_open(path: str, **kwargs) -> int:
    """
    Get O_PATH open for specified `path`. Supports following kwargs:

    `dir_fd` - fileno for open of to use as dir_fd for open of path.

    `expected_mode` - expected permissions on open of `path`. If
    the `force` kwarg is also set then the file's permissions
    will be changed to the specified value. Otherwise ValueError
    will be raised on permissions mismatch.

    `force` - If path is a symbolic link, then the symlink will be
    removed and replaced with a directory. In case of mismatch
    between expected_mode and stat() output, chmod(2) will be called.

    `mkdir` - if `path` does not exist, then it will be created.
    """
    dir_fd = kwargs.get('dir_fd')
    flags = os.O_PATH | os.O_NOFOLLOW | kwargs.get('additional_flags', 0)
    expected_mode = kwargs.get('mode')
    force = kwargs.get('force')
    mkdir = kwargs.get('mkdir', False)
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
            tmp_fd = pathref_reopen(fd, os.O_DIRECTORY, dir_fd=dir_fd)
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


def is_child_realpath(child: str, parent: str):
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


def is_child(child: str, parent: str):
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


def should_exclude(dataset: str, exclude: [str]):
    return any(is_child(dataset, excl) for excl in exclude)
