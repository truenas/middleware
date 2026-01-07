import os
import logging
import truenas_os

logger = logging.getLogger(__name__)

__all__ = ["getmntinfo", "iter_mountinfo", "statmount"]


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
