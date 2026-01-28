import os
import logging
import truenas_os

logger = logging.getLogger(__name__)

__all__ = ["getmntinfo", "iter_mountinfo", "statmount", "umount"]


def __parse_mnt_attr(attr: int) -> list:
    out = []
    if attr & truenas_os.MOUNT_ATTR_NOATIME:
        out.append('NOATIME')

    if attr & truenas_os.MOUNT_ATTR_RELATIME:
        out.append('RELATIME')

    if attr & truenas_os.MOUNT_ATTR_NOSUID:
        out.append('NOSUID')

    if attr & truenas_os.MOUNT_ATTR_NODEV:
        out.append('NODEV')

    if attr & truenas_os.MOUNT_ATTR_NOEXEC:
        out.append('NOEXEC')

    if attr & truenas_os.MOUNT_ATTR_RDONLY:
        out.append('RO')
    else:
        out.append('RW')

    if attr & truenas_os.MOUNT_ATTR_IDMAP:
        out.append('IDMAP')

    if attr & truenas_os.MOUNT_ATTR_NOSYMFOLLOW:
        out.append('NOSYMFOLLOW')

    return out


def __statmount_dict(sm: truenas_os.StatmountResult) -> dict:
    return {
        'mount_id': sm.mnt_id,
        'parent_id': sm.mnt_parent_id,
        'device_id': {
            'major': sm.sb_dev_major,
            'minor': sm.sb_dev_minor,
            'dev_t': os.makedev(sm.sb_dev_major, sm.sb_dev_minor)
        },
        'root': sm.mnt_root,
        'mountpoint': sm.mnt_point,
        'mount_opts': __parse_mnt_attr(sm.mnt_attr),
        'fs_type': sm.fs_type,
        'mount_source': sm.sb_source,
        'super_opts': sm.mnt_opts.upper().split(',') if sm.mnt_opts else []
    }



def iter_mountinfo(
    *, target_mnt_id: int | None = None,
    reverse: bool = False,
    as_dict: bool = True
):
    """
    Iterate mountpoints on the server. If `target_mnt_id` is provided then only children of the specified mount id
    will be iterated. If `reverse` is specified, then they will be iterated in reverse order. If `as_dict` is
    specified, then iterator will yield dictionary of legacy format.
    """
    iter_kwargs = {'reverse': reverse, 'statmount_flags': truenas_os.STATMOUNT_ALL}
    if target_mnt_id:
        iter_kwargs['mnt_id'] = target_mnt_id

    for sm in truenas_os.iter_mount(**iter_kwargs):
        if as_dict:
            yield __statmount_dict(sm)
        else:
            yield sm


def statmount(
    *,
    path: str|None = None,
    fd: int|None = None,
    as_dict: bool = True
) -> dict|truenas_os.StatmountResult:
    """
    Get mount information about the given path or open file. If as_dict
    is set, then we return a dictionary with same keys and formatting
    as previous getmntinfo() call.
    """
    if (not path and not fd) or (path and fd):
        raise ValueError('One of path or fd is required')

    if path:
        mnt_id = truenas_os.statx(path, mask=truenas_os.STATX_MNT_ID_UNIQUE).stx_mnt_id
    else:
        mnt_id = truenas_os.statx(
            '', dir_fd=fd, flags=truenas_os.AT_EMPTY_PATH, mask=truenas_os.STATX_MNT_ID_UNIQUE
        ).stx_mnt_id

    sm = truenas_os.statmount(mnt_id, mask=truenas_os.STATMOUNT_ALL)
    if not as_dict:
        return sm

    return __statmount_dict(sm)


def getmntinfo(mnt_id=None):
    """
    Get mount information. Takes the following arguments for faster lookup of
    information for a mounted filesystem.

    `mnt_id` - specify the unique ID for the mount. This is unique only for the
    lifetime of the mount. statx() may be used to retrieve the mnt_id for a given
    path or open file. If specified results are a dictionary indexed by mnt_id.

    Each result entry contains the following keys (from proc(5)):

    `mount_id` - unique id for a mount (may be reused after umount(2))

    `parent_id` - mount_id of the parent mount. A parent_id of `1` indicates the
    root of the mount tree.

    `device_id` - dictionary containing the value of `st_dev` for files in this
    filesystem.

    `root` - the pathname of the directory in the filesystem which forms the
    root of this mount.

    `mountpoint` - the pathname of the mountpoint relative to the root directory.

    `mount_opts` - per-mount options (see mount(2)).

    `fstype` - the filesystem type.

    `mount_source` - filesystem-specific information or "none". In case of ZFS
    this contains dataset name.

    `super_opts` - per-superblock options (see mount(2)).
    """
    info = {}
    # special handling for mnt_id
    if mnt_id:
        sm = truenas_os.statmount(mnt_id)
        info[mnt_id] = __statmount_dict(sm)
    else:
        for entry in iter_mountinfo():
            mnt_id = entry['mount_id']
            info[mnt_id] = entry

    return info


def umount(
    path: str,
    *,
    force: bool = False,
    detach: bool = False,
    expire: bool = False,
    follow_symlinks: bool = False,
    recursive: bool = False
) -> None:
    """
    Unmount filesystem at the given path.

    Args:
        path: Path to the mountpoint to unmount
        force: If True, force unmount even if busy (MNT_FORCE)
        detach: If True, lazy unmount - detach from filesystem hierarchy immediately (MNT_DETACH)
        expire: If True, mark the mount as expired (MNT_EXPIRE)
        follow_symlinks: If True, follow symlinks. If False, don't follow symlinks (UMOUNT_NOFOLLOW)
        recursive: If True, recursively unmount all child mounts before unmounting the target

    Raises:
        ValueError: If target is not a mountpoint or if expire was specified with either force or detach
        OSError: See umount2(2) manpage for errno explanations
        FileNotFoundError: If path does not exist

    Examples:
        umount('/mnt/pool')  # Basic unmount
        umount('/mnt/pool', force=True)  # Force unmount even if busy
        umount('/mnt/pool', detach=True)  # Lazy unmount
        umount('/mnt/pool', force=True, detach=True)  # Force and detach
        umount('/mnt/pool', recursive=True)  # Recursively unmount children first

    NOTE:
        MNT_FORCE is a no-op on most filesystems (including ZFS)
    """
    # Build flags from boolean arguments
    flags = 0
    if force:
        flags |= truenas_os.MNT_FORCE
    if detach:
        flags |= truenas_os.MNT_DETACH
    if expire:
        flags |= truenas_os.MNT_EXPIRE
    if not follow_symlinks:
        flags |= truenas_os.UMOUNT_NOFOLLOW

    if recursive:
        # Get the mount ID of the target path and verify it's a mountpoint
        stat_result = truenas_os.statx(path, mask=truenas_os.STATX_MNT_ID_UNIQUE | truenas_os.STATX_BASIC_STATS)
        if not (stat_result.stx_attributes & truenas_os.STATX_ATTR_MOUNT_ROOT):
            raise ValueError(f'{path!r} is not a mountpoint')

        mnt_id = stat_result.stx_mnt_id

        # Unmount all child mounts first
        for mnt in iter_mountinfo(target_mnt_id=mnt_id, reverse=True):
            truenas_os.umount2(target=mnt['mountpoint'], flags=flags)

    # Unmount the target path itself
    truenas_os.umount2(target=path, flags=flags)


def move_tree(
    source_path: str,
    destination_path: str,
    *,
    open_tree_flags: int = truenas_os.OPEN_TREE_CLOEXEC,
    move_mount_flags: int = truenas_os.MOVE_MOUNT_BENEATH
):
    """
    Atomically move a mount tree from source to destination.

    This uses open_tree() to get a handle to the source mount tree, then
    move_mount() to atomically place it at the destination. When using
    MOVE_MOUNT_BENEATH, the new mount is placed underneath any existing
    mount at the destination.

    Args:
        source_path: Path to the source mount tree
        destination_path: Path where the mount tree should be moved
        open_tree_flags: Flags for open_tree() (default: OPEN_TREE_CLOEXEC)
        move_mount_flags: Flags for move_mount() (default: MOVE_MOUNT_BENEATH)
                         Will be ORed with MOVE_MOUNT_F_EMPTY_PATH

    Raises:
        Any exception from open_tree() or move_mount()

    Example:
        # Atomically replace /system with contents from /tmp/newsystem
        move_tree('/tmp/newsystem', '/system')
        # Caller should then unmount the old layer if using MOVE_MOUNT_BENEATH
    """
    tree_fd = truenas_os.open_tree(
        path=source_path,
        flags=open_tree_flags
    )

    try:
        truenas_os.move_mount(
            from_dirfd=tree_fd,
            from_path="",
            to_path=destination_path,
            flags=truenas_os.MOVE_MOUNT_F_EMPTY_PATH | move_mount_flags
        )
    finally:
        os.close(tree_fd)
