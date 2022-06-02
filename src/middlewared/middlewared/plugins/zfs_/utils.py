# -*- coding=utf-8 -*-
import enum
import logging
import os

logger = logging.getLogger(__name__)

__all__ = ["zvol_name_to_path", "zvol_path_to_name"]


class ZFSCTL(enum.IntEnum):
    # from include/os/linux/zfs/sys/zfs_ctldir.h in ZFS repo
    INO_ROOT = 0x0000FFFFFFFFFFFF
    INO_SNAPDIR = 0x0000FFFFFFFFFFFD


def zvol_name_to_path(name):
    return os.path.join("/dev/zvol", name.replace(" ", "+"))


def zvol_path_to_name(path):
    if not path.startswith("/dev/zvol/"):
        raise ValueError(f"Invalid zvol path: {path!r}")

    return path[len("/dev/zvol/"):].replace("+", " ")


def unlocked_zvols_fast(options=None, data=None):
    """
    Get zvol information from /sys/block and /dev/zvol.
    This is quite a bit faster than using py-libzfs.

    supported options:
    `SIZE` - size of zvol
    `DEVID` - the device id of the zvol
    `RO` - whether zvol is flagged as ro (snapshot)
    `ATTACHMENT` - where zvol is currently being used

    If 'ATTACHMENT' is used, then dict of attachemnts
    should be provided under `data` key `attachments`
    """
    def get_size(zvol_dev):
        with open(f'/sys/block/{zvol_dev}/size', 'r') as f:
            nblocks = f.readline()

        return int(nblocks[:-1]) * 512

    def get_devid(zvol_dev):
        with open(f'/sys/block/{zvol_dev}/dev', 'r') as f:
            devid = f.readline()
        return devid[:-1]

    def get_ro(zvol_dev):
        with open(f'/sys/block/{zvol_dev}/ro', 'r') as f:
            ro = f.readline()
        return ro[:-1] == '1'

    def get_attachment(zvol_vdev, data):
        out = None
        for method, attachment in data.items():
            val = attachment.pop(zvol_vdev, None)
            if val is not None:
                out = {
                    'method': method,
                    'data': val
                }
                break

        return out

    def get_zvols(info_level, data):
        out = {}
        zvol_path = '/dev/zvol/'
        do_get_size = 'SIZE' in info_level
        do_get_dev = 'DEVID' in info_level
        do_get_ro = 'RO' in info_level
        do_get_attachment = 'ATTACHMENT' in info_level

        for root, dirs, files in os.walk(zvol_path):
            if not files:
                continue

            for file in files:
                path = root + '/' + file
                zvol_name = zvol_path_to_name(path)
                dev_name = os.readlink(path).split('/')[-1]

                out.update({
                    zvol_name: {
                        'path': path,
                        'name': zvol_name,
                        'dev': dev_name,
                    }
                })

                if do_get_size is True:
                    out[zvol_name]['size'] = get_size(dev_name)

                if do_get_dev is True:
                    out[zvol_name]['devid'] = get_devid(dev_name)

                if do_get_ro is True:
                    out[zvol_name]['ro'] = get_ro(dev_name)

                if do_get_attachment:
                    out[zvol_name]['attachment'] = get_attachment(zvol_name, data.get('attachments', {}))

        return out

    info_level = options or []
    zvols = get_zvols(info_level, data or {})
    return zvols
