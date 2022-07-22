import os

from middlewared.service import Service, private
from middlewared.schema import accepts, returns, Dict
from middlewared.plugins.zfs_.utils import ZFSCTL
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
        collapsed = []
        datasets = self.middleware.call_sync('pool.dataset.query', filters, options)
        for dataset in datasets:
            self.collapse_datasets(dataset, collapsed)

        mntinfo = getmntinfo()
        info = self.build_details(mntinfo)
        for i in collapsed:
            snapshot_count, locked = self.get_snapcount_and_encryption_status(i, mntinfo)
            i['snapshot_count'] = snapshot_count
            i['locked'] = locked
            i['nfs_shares'] = self.get_nfs_shares(i, info['nfs'])
            i['smb_shares'] = self.get_smb_shares(i, info['smb'])
            i['iscsi_shares'] = self.get_iscsi_shares(i, info['iscsi'])
            i['vms'] = self.get_vms(i, info['vm'])
            i['apps'] = self.get_apps(i,  info['app'])
            i['replication_tasks_count'] = self.get_repl_tasks_count(i, info['repl'])
            i['snapshot_tasks_count'] = self.get_snapshot_tasks_count(i, info['snap'])
            i['cloudsync_tasks_count'] = self.get_cloudsync_tasks_count(i, info['cloud'])
            i['rsync_tasks_count'] = self.get_rsync_tasks_count(i, info['rsync'])

        return datasets

    @private
    def collapse_datasets(self, dataset, collapsed):
        collapsed.append(dataset)
        for child in dataset.get('children', []):
            self.collapse_datasets(child, collapsed)

    @private
    def get_mount_info(self, path, mntinfo):
        mount_info = {}
        try:
            devid = os.stat(path).st_dev
        except Exception:
            # path deleted/umounted/locked etc
            pass
        else:
            if devid in mntinfo:
                mount_info = mntinfo[devid]

        return mount_info

    @private
    def build_details(self, mntinfo):
        results = {
            'iscsi': [], 'nfs': [], 'smb': [],
            'repl': [], 'snap': [], 'cloud': [],
            'rsync': [], 'vm': [], 'app': []
        }

        # iscsi
        t_to_e = self.middleware.call_sync('iscsi.targetextent.query')
        t = {i['id']: i for i in self.middleware.call_sync('iscsi.target.query')}
        e = {i['id']: i for i in self.middleware.call_sync('iscsi.extent.query')}
        for i in filter(lambda x: x['target'] in t and t[x['target']]['groups'] and x['extent'] in e, t_to_e):
            """
            1. make sure target's and extent's id exist in the target to extent table
            2. make sure the target has `groups` entry since, without it, it's impossible
                that it's being shared via iscsi
            """
            results['iscsi'].append({
                'extent': e[i['extent']],
                'target': t[i['target']],
                'mount_info': self.get_mount_info(e[i['extent']]['path'], mntinfo),
            })

        # nfs and smb
        for key in ('nfs', 'smb'):
            for share in self.middleware.call_sync(f'sharing.{key}.query'):
                share['mount_info'] = self.get_mount_info(share['path'], mntinfo)
                results[key].append(share)

        # replication
        options = {'prefix': 'repl_'}
        for task in self.middleware.call_sync('datastore.query', 'storage.replication', [], options):
            # replication can only be configured on a dataset so getting mount info is unnecessary
            results['repl'].append(task)

        # snapshots
        for task in self.middleware.call_sync('datastore.query', 'storage.task', [], {'prefix': 'task_'}):
            # snapshots can only be configured on a dataset so getting mount info is unnecessary
            results['snap'].append(task)

        # cloud sync
        for task in self.middleware.call_sync('datastore.query', 'tasks.cloudsync'):
            task['mount_info'] = self.get_mount_info(task['path'], mntinfo)
            results['cloud'].append(task)

        # rsync
        for task in self.middleware.call_sync('rsynctask.query'):
            task['mount_info'] = self.get_mount_info(task['path'], mntinfo)
            results['rsync'].append(task)

        # vm
        for vm in self.middleware.call_sync('datastore.query', 'vm.device'):
            if vm['dtype'] not in ('RAW', 'DISK'):
                continue

            if vm['dtype'] == 'DISK':
                # disk type is always a zvol
                vm['zvol'] = vm['attributes']['path'].removeprefix('/dev/zvol/')
            else:
                # raw type is always a file
                vm['mount_info'] = self.get_mount_info(vm['attributes']['path'], mntinfo)

            results['vm'].append(vm)

        # app
        """
        FIXME: this call is too expensive. Mostly because it queries entirely too much
            information when we're only after the container name and any datasets on
            the host machine that the container is using. Without this method, the total
            time this method takes in worst case scenario (1k datasets, 15k snapshots,
            90 smb shares, 36 nfs shares, 20 iscsi shares) takes ~2.2-2.4 seconds. When
            adding this method, it baloons too ~4.1 seconds (with only 1 app). A separate
            endpoint will be added (eventually) that will be less expensive than this.
        options = {'extra': {'retrieve_resources': True}}
        for app in self.middleware.call_sync('chart.release.query', [], options):
            for i in app['resources']['host_path_volumes']:
                path = i['host_path']['path']
                if 'ix-applications/' in path:
                    continue

                i['mount_info'] = self.get_mount_info(path, mntinfo)

            results['app'].append(app)
        """

        return results

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
    def get_nfs_shares(self, ds, nfsshares):
        nfs_shares = []
        for share in nfsshares:
            if share['path'] == ds['mountpoint'] or share['mount_info'].get('mount_source') == ds['id']:
                nfs_shares.append({'enabled': share['enabled'], 'path': share['path']})

        return nfs_shares

    @private
    def get_smb_shares(self, ds, smbshares):
        smb_shares = []
        for share in smbshares:
            if share['path'] == ds['mountpoint'] or share['mount_info'].get('mount_source') == ds['id']:
                smb_shares.append({
                    'enabled': share['enabled'],
                    'path': share['path'],
                    'share_name': share['name']
                })

        return smb_shares

    @private
    def get_iscsi_shares(self, ds, iscsishares):
        iscsi_shares = []
        thick_provisioned = any((ds['reservation']['value'], ds['refreservation']['value']))
        for share in iscsishares:
            if share['extent']['type'] == 'DISK' and share['extent']['path'].removeprefix('zvol/') == ds['id']:
                # we store extent information prefixed with `zvol/` (i.e. zvol/tank/zvol01).
                iscsi_shares.append({
                    'enabled': share['extent']['enabled'],
                    'type': 'DISK',
                    'path': f'/dev/{share["extent"]["path"]}',
                    'thick_provisioned': thick_provisioned,
                })
            elif share['extent']['type'] == 'FILE' and share['mount_info'].get('mount_source') == ds['id']:
                # this isn't common but possible, you can share a "file"
                # via iscsi which means it's not a dataset but a file inside
                # a dataset so we need to find the source dataset for the file
                iscsi_shares.append({
                    'enabled': share['extent']['enabled'],
                    'type': 'FILE',
                    'path': share['extent']['path'],
                    'thick_provisioned': thick_provisioned,
                })

        return iscsi_shares

    @private
    def get_repl_tasks_count(self, ds, repltasks):
        count = 0
        for repl in filter(lambda x: x['direction'] == 'PUSH', repltasks):
            # we only care about replication tasks that are configured to push
            for src_ds in filter(lambda x: x == ds['id'], repl['source_datasets']):
                count += 1

        return count

    @private
    def get_snapshot_tasks_count(self, ds, snaptasks):
        return len([i for i in snaptasks if i['dataset'] == ds['id']])

    @private
    def get_cloudsync_tasks_count(self, ds, cldtasks):
        count = 0
        for i in filter(lambda x: x['direction'] == 'PUSH', cldtasks):
            # we only care about cloud sync tasks that are configured to push
            if i['mountpoint'] == ds['mountpoint'] or i['mount_info'].get('mount_source') == ds['id']:
                count += 1

        return count

    @private
    def get_rsync_tasks_count(self, ds, rsynctasks):
        count = 0
        for i in filter(lambda x: x['direction'] == 'PUSH', rsynctasks):
            # we only care about rsync tasks that are configured to push
            if i['path'] == ds['mountpoint'] or i['mount_info'].get('mount_source') == ds['id']:
                count += 1

        return count

    @private
    def get_vms(self, ds, _vms):
        vms = []
        for i in _vms:
            if (
                'zvol' in i and i['zvol'] == ds['id'] or
                i['attributes']['path'] == ds['mountpoint'] or
                i.get('mount_info', {}).get('mount_source') == ds['id']
            ):
                vms.append({'name': i['vm']['name'], 'path': i['attributes']['path']})

        return vms

    @private
    def get_apps(self, ds, _apps):
        apps = []
        for app in _apps:
            for i in app['resources']['host_path_volumes']:
                path = i['host_path']['path']
                if 'ix-applications/' in path:
                    continue

                if path == ds['mountpoint'] or i['mount_info'].get('mount_source') == ds['id']:
                    apps.append({'name': app['name'], 'path': path})

        return apps
