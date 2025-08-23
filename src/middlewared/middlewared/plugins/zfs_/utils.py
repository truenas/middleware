# -*- coding=utf-8 -*-
import enum
import logging
import os
import re

from middlewared.plugins.audit.utils import AUDIT_DEFAULT_FILL_CRITICAL, AUDIT_DEFAULT_FILL_WARNING
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils import BOOT_POOL_NAME_VALID
from middlewared.utils.filesystem.constants import ZFSCTL
from middlewared.utils.filesystem.stat_x import statx
from middlewared.utils.mount import getmntinfo
from middlewared.utils.path import is_child
from middlewared.utils.tdb import (
    get_tdb_handle,
    TDBBatchAction,
    TDBBatchOperation,
    TDBDataType,
    TDBOptions,
    TDBPathType,
)

logger = logging.getLogger(__name__)

__all__ = [
    "get_snapshot_count_cached",
    "path_to_dataset_impl",
    "paths_to_datasets_impl",
    "zvol_name_to_path",
    "zvol_path_to_name",
]

LEGACY_USERPROP_PREFIX = 'org.freenas'
USERPROP_PREFIX = 'org.truenas'
ZD_PARTITION = re.compile(r'zd[0-9]+p[0-9]+$')
SNAP_COUNT_TDB_NAME = 'snapshot_count'
SNAP_COUNT_TDB_OPTIONS = TDBOptions(TDBPathType.PERSISTENT, TDBDataType.JSON)


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


def get_snapshot_count_cached(middleware, lz, datasets, update_datasets=False, remove_snapshots_changed=False):
    """
    Try retrieving snapshot count for dataset from cache if the
    `snapshots_changed` timestamp hasn't changed. If it has,
    then retrieve new snapshot count in most optimized way possible
    and cache new value

    Parameters:
    ----------
    middleware - middleware object
    lz - libzfs handle, e.g. libzfs.ZFS()
    zhdl - iterable containing dataset information as returned by
        libzfs.datasets_serialized
    update_datasets - bool - optional - insert `snapshot_count` key into datasets passed
        into this method
    remove_snapshots_changed - bool - remove the snapshots_changed key from dataset properties
        after processing. This is to hide the fact that we had to retrieve this property to
        determine whether to return cached value.

    Returns:
    -------
    Dict containing following:
        key (dataset name) : value (int - snapshot count)
    """
    def get_mountpoint(zhdl):
        mp = zhdl['properties'].get('mountpoint')
        if mp is None:
            return None

        if mp['parsed'] and mp['parsed'] != 'legacy':
            return mp['parsed']

        return None

    def entry_get_cnt(zhdl):
        """
        Retrieve snapshot count in most efficient way possible. If dataset is mounted, then
        retrieve from st_nlink otherwise, iter snapshots from dataset handle
        """
        if mp := get_mountpoint(zhdl):
            try:
                st = os.stat(f'{mp}/.zfs/snapshot')
            except Exception:
                pass
            else:
                if st.st_ino == ZFSCTL.INO_SNAPDIR.value:
                    return st.st_nlink - 2

        return len(lz.snapshots_serialized(['name'], datasets=[zhdl['name']], recursive=False))

    def get_entry_fetch(key):
        """ retrieve cached snapshot count from persistent key-value store """
        try:
            with get_tdb_handle(SNAP_COUNT_TDB_NAME, SNAP_COUNT_TDB_OPTIONS) as hdl:
                entry = hdl.get(key)
        except MatchNotFound:
            entry = {
                'changed_ts': None,
                'cnt': -1
            }
        return entry

    def process_entry(out, zhdl, batch_ops):
        """
        This method processes the dataset entry and
        sets new value in tdb file if necessary. Since
        we may be consuming "flattened" datasets here, there
        is potential for duplicate entries. Hence, check for
        whether we've already handled the dataset for this run.
        """
        existing_entry = out.get(zhdl['name'])
        if existing_entry:
            if update_datasets:
                zhdl['snapshot_count'] = existing_entry

            if remove_snapshots_changed:
                zhdl['properties'].pop('snapshots_changed', None)

            return

        changed_ts = zhdl['properties']['snapshots_changed']['parsed']
        cache_key = f'SNAPCNT%{zhdl["name"]}'

        entry = get_entry_fetch(cache_key)

        if entry['changed_ts'] != changed_ts:
            entry['cnt'] = entry_get_cnt(zhdl)
            entry['changed_ts'] = changed_ts

            # There are circumstances in which legacy datasets
            # may not have this property populated. We don't
            # want cache insertion with NULL key to avoid
            # collisions
            if changed_ts:
                batch_ops.append(TDBBatchOperation(
                    action=TDBBatchAction.SET,
                    key=cache_key,
                    value=entry
                ))

        out[zhdl['name']] = entry['cnt']
        if update_datasets:
            zhdl['snapshot_count'] = entry['cnt']

        if remove_snapshots_changed:
            zhdl['properties'].pop('snapshots_changed', None)

    def iter_datasets(out, datasets_in, batch_ops):
        for ds in datasets_in:
            process_entry(out, ds, batch_ops)
            iter_datasets(out, ds.get('children', []), batch_ops)

    out = {}
    batch_ops = []

    iter_datasets(out, datasets, batch_ops)

    if batch_ops:
        # Commit changes to snapshot counts under a transaction lock
        try:
            with get_tdb_handle(SNAP_COUNT_TDB_NAME, SNAP_COUNT_TDB_OPTIONS) as hdl:
                hdl.batch_op(batch_ops)
        except Exception:
            logger.warning('Failed to update cached snapshot counts', exc_info=True)

    return out


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
