# -*- coding=utf-8 -*-
import enum
import logging
import os

from middlewared.service_exception import MatchNotFound

logger = logging.getLogger(__name__)

__all__ = ["zvol_name_to_path", "zvol_path_to_name", "get_snapshot_count_cached"]


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


def get_snapshot_count_cached(middleware, lz, datasets, prefetch=False, update_datasets=False, remove_snapshots_changed=False):
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
    prefetch - bool - optional performance enhancement to grab entire
        tdb contents prior to iteration. This reduces count of middleware calls.
    update_datasets - bool - optional - insert `snapshot_count` key into datasets passed
        into this method
    remove_snapshots_changed - bool - remove the snapshots_changed key from dataset properties
        after processing. This is to hide the fact that we had to retrieve this property to
        determie whether to return cached value.

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
        if mp := get_mountpoint(zhdl):
            try:
                st = os.stat(f'{mp}/.zfs/snapshot')
            except Exception:
                pass
            else:
                if st.st_ino == ZFSCTL.INO_SNAPDIR.value:
                    return st.st_nlink - 2

        return len(lz.snapshots_serialized(['name'], datasets=[zhdl['name']], recursive=False))

    def get_entry_prefetch(key, tdb_entries):
        return tdb_entries.get(key, {'changed_ts': None, 'cnt': -1})

    def get_entry_fetch(key, tdb_entries):
        try:
            entry = middleware.call_sync('tdb.fetch', {
                'name': 'snapshot_count',
                'key': key,
            })
        except MatchNotFound:
            entry = {
                'changed_ts': None,
                'cnt': -1
            }
        return entry

    def process_entry(out, zhdl, tdb_entries, batch_ops, get_entry_fn):
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

        entry = get_entry_fn(cache_key, tdb_entries)

        if entry['changed_ts'] != changed_ts:
            entry['cnt'] = entry_get_cnt(zhdl)
            entry['changed_ts'] = changed_ts

            # There are circumstances in which legacy datasets
            # may not have this property populated. We don't
            # want cache insertion with NULL key to avoid
            # collisions
            if changed_ts:
                batch_ops.append({
                    'action': 'SET',
                    'key': cache_key,
                    'val': entry
                })

        out[zhdl['name']] = entry['cnt']
        if update_datasets:
            zhdl['snapshot_count'] = entry['cnt']

        if remove_snapshots_changed:
            zhdl['properties'].pop('snapshots_changed', None)

    def iter_datasets(out, datasets_in, tdb_entries, batch_ops, get_entry_fn):
        for ds in datasets_in:
            process_entry(out, ds, tdb_entries, batch_ops, get_entry_fn)
            iter_datasets(out, ds.get('children', []), tdb_entries, batch_ops, get_entry_fn)

    tdb_entries = {}
    out = {}
    batch_ops = []
    get_entry_fn = get_entry_fetch
    if prefetch:
        tdb_entries = {
            x['key']: x['val']
            for x in middleware.call_sync('tdb.entries', {'name': 'snapshot_count'})
        }
        get_entry_fn = get_entry_prefetch

    iter_datasets(out, datasets, tdb_entries, batch_ops, get_entry_fn)
    if batch_ops:
        middleware.call_sync('tdb.batch_ops', {'name': 'snapshot_count', 'ops': batch_ops})

    return out
