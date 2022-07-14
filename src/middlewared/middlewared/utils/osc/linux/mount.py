# -*- coding=utf-8 -*-
import os
import logging

logger = logging.getLogger(__name__)

__all__ = ["getmntinfo"]


def __parse_mntent(line, out_dict):
    mnt_id, parent_id, maj_min, root, mp, opts, extra = line.split(" ", 6)
    fstype, mnt_src, super_opts = extra.split(' - ')[1].split()

    major, minor = maj_min.split(':')
    devid = os.makedev(int(major), int(minor))
    out_dict.update({devid: {
        'mount_id': int(mnt_id),
        'parent_id': int(parent_id),
        'device_id': {
            'major': int(major),
            'minor': int(minor),
            'dev_t': devid,
        },
        'root': root.replace('\\040', ' '),
        'mountpoint': mp.replace('\\040', ' '),
        'mount_opts': opts.upper().split(','),
        'fs_type': fstype,
        'mount_source': mnt_src.replace('\\040', ' '),
        'super_opts': super_opts.upper().split(','),
    }})


def getmntinfo_from_path(path):
    """
    Try to determine the `dev_id` (st_dev) from `path` and then
    call `getmntinfo` for O(1) lookups since mount info
    is keyed on `dev_id`.
    """
    dev_id = os.stat(path).st_dev
    return getmntinfo(dev_id=dev_id)[dev_id]


def getmntinfo(dev_id=None):
    """
    Get mount information. returns dictionary indexed by dev_t.
    User can optionally specify dev_t for faster lookup of single
    device.
    """
    if dev_id:
        maj_min = f'{os.major(dev_id)}:{os.minor(dev_id)}'
    else:
        maj_min = None

    out = {}
    with open('/proc/self/mountinfo') as f:
        for line in f:
            if maj_min:
                if line.find(maj_min) == -1:
                    continue

                __parse_mntent(line, out)
                break

            __parse_mntent(line, out)

    return out
