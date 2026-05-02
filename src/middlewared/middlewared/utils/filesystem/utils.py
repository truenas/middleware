# This file provides various utilities that don't fit cleanly
# into specific categories of filesystem areas.
#
# path_in_ctldir() has test coverage via api tests for filesystem.stat
# and filesystem.listdir methods since it requires access to zpool.

import os
from pathlib import Path

from truenas_os_pyutils.mount import statmount

from .constants import ZFSCTL


def path_in_ctldir(path_in: str | Path) -> bool:
    """
    Determine whether the given path is located within the ZFS
    ctldir. The intention for this is to determine whether a given
    path is inside a ZFS snapshot so that we can raise meaningful
    validation errors in situations like the user trying to set
    permissions on a file in a snapshot directory.
    """
    path = Path(path_in)
    if not path.is_absolute():
        raise ValueError(f'{path_in}: not an absolute path')

    is_in_ctldir = False
    while path.as_posix() != '/':
        if not path.name == '.zfs':
            path = path.parent
            continue

        if path.stat().st_ino == ZFSCTL.INO_ROOT:
            is_in_ctldir = True
            break

        path = path.parent

    return is_in_ctldir


def get_mount_info_for_path(path: str | os.PathLike) -> tuple[str, str, str | None]:
    """
    Resolve a directory path to the (mountpoint, filesystem_name, relative_path)
    triple required by ``truenas_os.iter_filesystem_contents``.

    Symlinks anywhere in the input are resolved before lookup so the helper can
    be used directly from path-only APIs (e.g. ``filesystem.listdir``).
    """
    real = os.path.realpath(os.fspath(path))
    sm = statmount(path=real, as_dict=False)
    rel = os.path.relpath(real, sm.mnt_point)
    return sm.mnt_point, sm.sb_source, (None if rel == '.' else rel)
