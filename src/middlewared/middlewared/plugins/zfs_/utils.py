import enum
import os
import re

from middlewared.plugins.audit.utils import AUDIT_DEFAULT_FILL_CRITICAL, AUDIT_DEFAULT_FILL_WARNING
from middlewared.service_exception import CallError
from middlewared.utils import BOOT_POOL_NAME_VALID
from middlewared.utils.filesystem.stat_x import statx
from middlewared.utils.mount import getmntinfo
from middlewared.utils.path import is_child

__all__ = [
    "path_to_dataset_impl",
    "paths_to_datasets_impl",
    "zvol_name_to_path",
    "zvol_path_to_name",
]

LEGACY_USERPROP_PREFIX = 'org.freenas'
USERPROP_PREFIX = 'org.truenas'
ZD_PARTITION = re.compile(r'zd[0-9]+p[0-9]+$')


class TNUserProp(enum.Enum):
    DESCRIPTION = f'{LEGACY_USERPROP_PREFIX}:description'
    QUOTA_WARN = f'{LEGACY_USERPROP_PREFIX}:quota_warning'
    QUOTA_CRIT = f'{LEGACY_USERPROP_PREFIX}:quota_critical'
    REFQUOTA_WARN = f'{LEGACY_USERPROP_PREFIX}:refquota_warning'
    REFQUOTA_CRIT = f'{LEGACY_USERPROP_PREFIX}:refquota_critical'
    MANAGED_BY = f'{USERPROP_PREFIX}:managedby'

    def default(self):
        match self:
            case TNUserProp.QUOTA_WARN:
                return AUDIT_DEFAULT_FILL_WARNING
            case TNUserProp.QUOTA_CRIT:
                return AUDIT_DEFAULT_FILL_CRITICAL
            case TNUserProp.REFQUOTA_WARN:
                return AUDIT_DEFAULT_FILL_WARNING
            case TNUserProp.REFQUOTA_CRIT:
                return AUDIT_DEFAULT_FILL_CRITICAL
            case _:
                raise ValueError(f'{self.value}: no default value is set')

    def quotas():
        return [(a.value, a.default()) for a in [
            TNUserProp.QUOTA_WARN,
            TNUserProp.QUOTA_CRIT,
            TNUserProp.REFQUOTA_WARN,
            TNUserProp.REFQUOTA_CRIT
        ]]

    def values():
        return [a.value for a in TNUserProp]


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

                try:
                    dev_name = os.readlink(path).split('/')[-1]
                except Exception:
                    # this happens if the file is a regular file
                    # saw this happend when a user logged into a system
                    # via ssh and tried to "copy" a zvol using "dd" on
                    # the cli and made a typo in the command. This created
                    # a regular file. When we readlink() that file, it
                    # crashed with OSError 22 Invalid Argument so we just
                    # skip this file
                    continue

                if ZD_PARTITION.match(dev_name):
                    continue

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


def paths_to_datasets_impl(
    paths: list[str],
    mntinfo: dict | None = None
) -> dict | dict[str, str | None]:
    """
    Convert `paths` to a dictionary of ZFS dataset names. This
    performs lookup through mountinfo.

    Anticipated error conditions are that paths are not
    on ZFS or if the boot pool underlies the path. In
    addition to this, all the normal exceptions that
    can be raised by a failed call to os.stat() are
    possible. If any exception occurs, the dataset name
    will be set to None in the dictionary.
    """
    rv = dict()
    if mntinfo is None:
        mntinfo = getmntinfo()

    for path in paths:
        try:
            rv[path] = path_to_dataset_impl(path, mntinfo)
        except Exception:
            rv[path] = None

    return rv


def path_to_dataset_impl(path: str, mntinfo: dict | None = None) -> str:
    """
    Convert `path` to a ZFS dataset name. This
    performs lookup through mountinfo.

    Anticipated error conditions are that path is not
    on ZFS or if the boot pool underlies the path. In
    addition to this, all the normal exceptions that
    can be raised by a failed call to os.stat() are
    possible.
    """
    stx = statx(path)
    if mntinfo is None:
        mntinfo = getmntinfo(stx.stx_mnt_id)[stx.stx_mnt_id]
    else:
        mntinfo = mntinfo[stx.stx_mnt_id]

    ds_name = mntinfo['mount_source']
    if mntinfo['fs_type'] != 'zfs':
        raise CallError(f'{path}: path is not a ZFS filesystem')

    for bp_name in BOOT_POOL_NAME_VALID:
        if is_child(ds_name, bp_name):
            raise CallError(f'{path}: path is on boot pool')

    return ds_name
