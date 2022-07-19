import os

from middlewared.service import Service, private
from middlewared.schema import accepts, returns, Dict
from middlewared.plugins.zfs_.utils import ZFSCTL
from middlewared.utils.path import belongs_to_tree, is_child
from middlewared.utils.osc.linux.mount import getmntinfo


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @accepts()
    @returns(Dict('datasets', additional_attrs=True))
    def details(self):
        filters = []
        options = {
            'extra': {
                'flat': False,
                'order_by': 'name',
                'properties': [
                    'used',
                    'available',
                    'usedbysnapshots',
                    'usedbydataset',
                    'usedbychildren',
                    'refquota',
                    'quota',
                    'refreservation',
                    'reservation',
                    'mountpoint',
                    'encryption',
                ]
            }
        }

        mntinfo = getmntinfo()
        nfsshares = self.middleware.call_sync('sharing.nfs.query')
        smbshares = self.middleware.call_sync('sharing.smb.query')
        repltasks = self.middleware.call_sync('datastore.query', 'storage.replication', [], {'prefix': 'repl_'})
        snaptasks = self.middleware.call_sync('datastore.query', 'storage.task', [], {'prefix': 'task_'})
        cldtasks = self.middleware.call_sync('datastore.query', 'tasks.cloudsync')
        collapsed = []
        info = self.middleware.call_sync('pool.dataset.query', filters, options)
        for dataset in info:
            self.collapse_datasets(dataset, collapsed)

        for i in collapsed:
            snapshot_count, locked = self.get_snapcount_and_encryption_status(i, mntinfo)
            i['snapshot_count'] = snapshot_count
            i['locked'] = locked
            i['nfs_shares'] = self.get_nfs_shares(i, nfsshares, mntinfo)
            i['smb_shares'] = self.get_smb_shares(i, smbshares, mntinfo)
            i['replication_tasks_count'] = self.get_repl_tasks_count(i, repltasks)
            i['snapshot_tasks_count'] = self.get_snapshot_tasks_count(i, snaptasks)
            i['cloudsync_tasks_count'] = self.get_cloudsync_tasks_count(i, cldtasks)

        return info

    @private
    def collapse_datasets(self, dataset, collapsed):
        collapsed.append(dataset)
        for child in dataset.get('children', []):
            self.collapse_datasets(child, collapsed)

    @private
    def get_snapcount_and_encryption_status(self, ds, mntinfo):
        snap_count = 0
        locked = False
        if ds['type'] == 'FILESYSTEM':
            # FIXME: determining zvol snapshot count requires iterating over
            # all snapshots for a given zvol and then counting them which is
            # painful. This will be moot when this is merged upstream
            # https://github.com/openzfs/zfs/pull/13635

            try:
                st = os.stat(f'{ds["mountpoint"]}/.zfs/snapshot')
            except FileNotFoundError:
                # means that the zfs snapshot dir doesn't exist which
                # can only happen if the dataset is encrypted and "locked"
                # (unmounted) or the dataset is unmounted
                locked = ds['encrypted']
            else:
                if st.st_ino == ZFSCTL.INO_SNAPDIR:
                    # dataset isn't locked and the inode of the snapshot dir
                    # is what we expect so we're able to determine the snapshot
                    # count by reading st_nlink
                    snap_count = st.st_nlink - 2  # (remove 2 for `.` and `..`)
                else:
                    # zfs snapshot dir exists but inode doesn't match reality
                    # which can only happen if dataset is unmounted and the
                    # same directory structure is created manually
                    locked = ds['encrypted']

        return snap_count, locked

    @private
    def get_nfs_shares(self, ds, nfsshares, mntinfo):
        nfs_shares = []
        found = False
        for nfsshare in nfsshares:
            if nfsshare['path'] == ds['mountpoint']:
                # the share path is the actual dataset
                found = True
            else:
                try:
                    devid = os.stat(nfsshare['path']).st_dev
                except Exception:
                    pass
                else:
                    found = devid in mntinfo and mntinfo[devid]['mount_source'] == ds['id']

            if found:
                nfs_shares.append({
                    'enabled': nfsshare['enabled'],
                    'path': nfsshare['path'],
                })

        return nfs_shares

    @private
    def get_smb_shares(self, ds, smbshares, mntinfo):
        smb_shares = []
        found = False
        for smbshare in smbshares:
            if smbshare['path'] == ds['mountpoint']:
                # the share path is the actual dataset
                found = True
            else:
                try:
                    devid = os.stat(smbshare['path']).st_dev
                except Exception:
                    pass
                else:
                    found = devid in mntinfo and mntinfo[devid]['mount_source'] == ds['id']

            if found:
                smb_shares.append({
                    'enabled': smbshare['enabled'],
                    'path': smbshare['path'],
                    'share_name': smbshare['name'],
                })

        return smb_shares

    @private
    def get_repl_tasks_count(self, ds, repltasks):
        count = 0
        for repl in repltasks:
            if repl['transport'] == 'LOCAL' or repl['direction'] == 'PUSH':
                if any(
                    belongs_to_tree(ds, src_ds, repl['recursive'], repl['exclude'])
                    for src_ds in repl['source_datasets']
                ):
                    count += 1

            if repl['transport'] == 'LOCAL' or repl['direction'] == 'PULL':
                if is_child(ds, repl['target_dataset']):
                    count += 1

        return count

    @private
    def get_cloudsync_tasks_count(self, ds, cldtasks):
        return len([i for i in cldtasks if i['path'] == ds['mountpoint']])

    @private
    def get_snapshot_tasks_count(self, ds, snaptasks):
        return len([i for i in snaptasks if f'/mnt/{i["dataset"]}' == ds['mountpoint']])
