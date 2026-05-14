import errno
import os

import truenas_os


def _open_dir_no_symlinks(fs_path: str) -> int:
    return truenas_os.openat2(fs_path, os.O_DIRECTORY, resolve=truenas_os.RESOLVE_NO_SYMLINKS)


def _apply_perms(fd: int, mode: int, uid: int, gid: int) -> None:
    st = os.fstat(fd)
    if st.st_uid != uid or st.st_gid != gid:
        os.fchown(fd, uid, gid)
    if (st.st_mode & 0o7777) != mode:
        os.fchmod(fd, mode)


def enforce_dir_perms(fs_path: str, mode: int = 0o700, uid: int = 0, gid: int = 0) -> None:
    """
    Symlink-safe ownership + mode enforcement for a directory.

    Opens `fs_path` with openat2(O_DIRECTORY, RESOLVE_NO_SYMLINKS) so subsequent
    fd-based syscalls cannot be redirected by a concurrent symlink swap.
    Stat-first: a steady-state call (already-correct dir) issues no chown/chmod.
    """
    fd = _open_dir_no_symlinks(fs_path)
    try:
        _apply_perms(fd, mode, uid, gid)
    finally:
        os.close(fd)


def enforce_mountpoint_perms(fs_path: str, mode: int = 0o700, uid: int = 0, gid: int = 0) -> None:
    """
    Same as enforce_dir_perms plus a mountpoint guard via STATX_ATTR_MOUNT_ROOT.

    If the target is not a mount root, raises OSError(ENOTDIR). Setting perms
    on a stale dir whose mode vanishes on remount is worse than failing loudly.
    """
    fd = _open_dir_no_symlinks(fs_path)
    try:
        st = truenas_os.statx(
            '', dir_fd=fd, flags=truenas_os.AT_EMPTY_PATH,
            mask=truenas_os.STATX_BASIC_STATS,
        )
        if not (st.stx_attributes & truenas_os.STATX_ATTR_MOUNT_ROOT):
            raise OSError(errno.ENOTDIR, f'{fs_path!r} is not a mountpoint')
        _apply_perms(fd, mode, uid, gid)
    finally:
        os.close(fd)
