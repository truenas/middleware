import os
import logging

logger = logging.getLogger(__name__)

__all__ = ["getmntinfo", "getmnttree"]


def __mntent_dict(line):
    mnt_id, parent_id, maj_min, root, mp, opts, extra = line.split(" ", 6)
    fstype, mnt_src, super_opts = extra.split(' - ')[1].split()

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


def __parse_to_dev(line, out_dict):
    entry = __mntent_dict(line)
    out_dict.update({entry['device_id']['dev_t']: entry})


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


def getmntinfo(dev_id=None, mnt_id=None):
    """
    Get mount information. returns dictionary indexed by dev_t.
    User can optionally specify dev_t for faster lookup of single
    device.
    """
    info = {}
    if mnt_id:
        __iter_mountinfo(mnt_id=mnt_id, callback=__parse_to_mnt_id, private_data=info)
    else:
        __iter_mountinfo(dev_id=dev_id, callback=__parse_to_dev, private_data=info)

    return info


def getmnttree(mount_id=None):
    """
    Generate a mount info tree of either the root filesystem
    or a given filesystem specified by dev_t.
    """
    info = {}
    __iter_mountinfo(callback=__parse_to_mnt_id, private_data=info)
    return __create_tree(info, mount_id)
