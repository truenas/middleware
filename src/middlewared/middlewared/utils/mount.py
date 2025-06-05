import os
import logging

logger = logging.getLogger(__name__)

__all__ = ["getmntinfo", "getmnttree"]


def __mntent_dict(line):
    mnt_id, parent_id, maj_min, root, mp, opts, extra = line.split(" ", 6)
    fstype, mnt_src, super_opts = extra.strip().split('- ')[1].split()

    major, minor = maj_min.split(':')
    devid = os.makedev(int(major), int(minor))

    return {
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
    }


def __parse_to_mnt_id(line, out_dict):
    entry = __mntent_dict(line)
    out_dict.update({entry['mount_id']: entry})


def __create_tree(info, mount_id):
    root_id = None

    for entry in info.values():
        if not entry.get('children'):
            entry['children'] = []

        if entry['parent_id'] == 1:
            root_id = entry['mount_id']
            continue

        parent = info[entry['parent_id']]
        if not parent.get('children'):
            parent['children'] = [entry]
        else:
            parent['children'].append(entry)

    return info[mount_id or root_id]


def __iter_mountinfo(dev_id=None, mnt_id=None, callback=None, private_data=None):
    if dev_id:
        maj_min = f'{os.major(dev_id)}:{os.minor(dev_id)}'
    else:
        maj_min = None

    if mnt_id:
        mount_id = f'{mnt_id} '

    with open('/proc/self/mountinfo') as f:
        for line in f:
            try:
                if maj_min:
                    if line.find(maj_min) == -1:
                        continue

                    callback(line, private_data)
                    break
                elif mnt_id is not None:
                    if not line.startswith(mount_id):
                        continue

                    callback(line, private_data)
                    break

                callback(line, private_data)
            except Exception as e:
                raise RuntimeError(f'Failed to parse {line!r} line: {e}')


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
    __iter_mountinfo(mnt_id=mnt_id, callback=__parse_to_mnt_id, private_data=info)
    return info


def getmnttree(mount_id=None):
    """
    Generate a mount info tree of either the root filesystem or a given
    filesystem specified by mnt_id. cf. documentation for getmntinfo().
    """
    info = {}
    __iter_mountinfo(callback=__parse_to_mnt_id, private_data=info)
    return __create_tree(info, mount_id)
