import os
import pathlib

from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.service import Service, private
from middlewared.schema import accepts, List, returns
from middlewared.utils.osc.linux.mount import getmntinfo


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @accepts()
    @returns(List(
        'dataset_details',
        example=[{
            'id': 'tank',
            'type': 'FILESYSTEM',
            'name': 'tank',
            'pool': 'tank',
            'encrypted': False,
            'encryption_root': None,
            'key_loaded': False,
            'children': [
                {
                    'id': 'tank/soemthing',
                    'type': 'VOLUME',
                    'name': 'tank/soemthing',
                    'pool': 'tank',
                    'encrypted': False,
                    'encryption_root': None,
                    'key_loaded': False,
                    'children': [],
                    'managed_by': {
                        'value': '10.231.1.155',
                        'rawvalue': '10.231.1.155',
                        'source': 'LOCAL',
                        'parsed': '10.231.1.155'
                    },
                    'quota_warning': {'value': '80', 'rawvalue': '80', 'source': 'LOCAL', 'parsed': '80'},
                    'quota_critical': {'value': '95', 'rawvalue': '95', 'source': 'LOCAL', 'parsed': '95'},
                    'refquota_warning': {'value': '80', 'rawvalue': '80', 'source': 'LOCAL', 'parsed': '80'},
                    'refquota_critical': {'value': '95', 'rawvalue': '95', 'source': 'LOCAL', 'parsed': '95'},
                    'reservation': {
                        'parsed': None, 'rawvalue': '0', 'value': None, 'source': 'DEFAULT', 'source_info': None
                    },
                    'refreservation': {
                        'parsed': None, 'rawvalue': '0', 'value': None, 'source': 'DEFAULT', 'source_info': None
                    },
                    'key_format': {
                        'parsed': 'none', 'rawvalue': 'none', 'value': None, 'source': 'DEFAULT', 'source_info': None
                    },
                    'volsize': {
                        'parsed': 57344, 'rawvalue': '57344', 'value': '56K', 'source': 'LOCAL', 'source_info': None
                    },
                    'encryption_algorithm': {
                        'parsed': 'off', 'rawvalue': 'off', 'value': None, 'source': 'DEFAULT', 'source_info': None
                    },
                    'used': {
                        'parsed': 57344, 'rawvalue': '57344', 'value': '56K', 'source': 'NONE', 'source_info': None
                    },
                    'usedbychildren': {
                        'parsed': 0, 'rawvalue': '0', 'value': '0B', 'source': 'NONE', 'source_info': None
                    },
                    'usedbydataset': {
                        'parsed': 57344, 'rawvalue': '57344', 'value': '56K', 'source': 'NONE', 'source_info': None
                    },
                    'usedbysnapshots': {
                        'parsed': 0, 'rawvalue': '0', 'value': '0B', 'source': 'NONE', 'source_info': None
                    },
                    'available': {
                        'parsed': 14328811520, 'rawvalue': '14328811520',
                        'value': '13.3G', 'source': 'NONE', 'source_info': None
                    },
                    'mountpoint': '/mnt/tank/something',
                    'sync': {
                        'parsed': 'standard', 'rawvalue': 'standard',
                        'value': 'STANDARD', 'source': 'DEFAULT', 'source_info': None
                    },
                    'compression': {
                        'parsed': 'lz4', 'rawvalue': 'lz4',
                        'value': 'LZ4', 'source': 'INHERITED', 'source_info': 'tank',
                    },
                    'deduplication': {
                        'parsed': 'on', 'rawvalue': 'on',
                        'value': 'ON', 'source': 'LOCAL', 'source_info': None,
                    },
                    'user_properties': {},
                    'snapshot_count': 0,
                    'locked': False,
                    'thick_provisioned': True,
                    'nfs_shares': [{
                        'enabled': True,
                        'path': '/mnt/tank/something'
                    }],
                    'smb_shares': [{
                        'enabled': False,
                        'path': '/mnt/tank/something/smbshare01',
                        'share_name': 'Home Pictures',
                    }],
                    'iscsi_shares': [{
                        'enabled': False,
                        'type': 'DISK',
                        'path': '/mnt/tank/something',
                    }],
                    'vms': [{
                        'name': 'deb01',
                        'path': '/dev/zvol/tank/something',
                    }],
                    'apps': [{
                        'name': 'diskoverdata',
                        'path': '/mnt/tank/something'
                    }],
                    'replication_tasks_count': 0,
                    'snapshot_tasks_count': 0,
                    'cloudsync_tasks_count': 0,
                    'rsync_tasks_count': 0
                }
            ],
            'mountpoint': '/mnt/tank',
            'quota': {'parsed': None, 'rawvalue': '0', 'value': None, 'source': 'DEFAULT', 'source_info': None},
            'refquota': {'parsed': None, 'rawvalue': '0', 'value': None, 'source': 'DEFAULT', 'source_info': None},
            'reservation': {'parsed': None, 'rawvalue': '0', 'value': None, 'source': 'DEFAULT', 'source_info': None},
            'refreservation': {
                'parsed': None, 'rawvalue': '0', 'value': None, 'source': 'DEFAULT', 'source_info': None
            },
            'encryption_algorithm': {
                'parsed': 'off', 'rawvalue': 'off', 'value': None, 'source': 'DEFAULT', 'source_info': None
            },
            'origin': {
                'parsed': '', 'rawvalue': '', 'value': '', 'source': 'NONE', 'source_info': None
            },
            'used': {
                'parsed': 3874467840, 'rawvalue': '3874467840', 'value': '3.61G', 'source': 'NONE', 'source_info': None
            },
            'usedbychildren': {
                'parsed': 3874369536, 'rawvalue': '3874369536', 'value': '3.61G', 'source': 'NONE', 'source_info': None
            },
            'usedbydataset': {
                'parsed': 98304, 'rawvalue': '98304', 'value': '96K', 'source': 'NONE', 'source_info': None
            },
            'usedbysnapshots': {'parsed': 0, 'rawvalue': '0', 'value': '0B', 'source': 'NONE', 'source_info': None},
            'available': {
                'parsed': 14328811520, 'rawvalue': '14328811520',
                'value': '13.3G', 'source': 'NONE', 'source_info': None
            },
            'user_properties': {},
            'snapshot_count': 0,
            'locked': False,
            'atime': False,
            'casesensitive': True,
            'readonly': False,
            'nfs_shares': [],
            'smb_shares': [],
            'iscsi_shares': [],
            'vms': [],
            'apps': [{
                'name': 'plex',
                'path': '/mnt/evo/data',
            }],
            'replication_tasks_count': 0,
            'snapshot_tasks_count': 0,
            'cloudsync_tasks_count': 0,
            'rsync_tasks_count': 0,
        }]
    ))
    def details(self):
        """
        Retrieve all dataset(s) details outlining any services/tasks which might be consuming the dataset(s).
        """
        options = {
            'extra': {
                'flat': True,
                'order_by': 'name',
                'properties': [
                    'used',
                    'available',
                    'usedbysnapshots',
                    'usedbydataset',
                    'usedbychildren',
                    'refquota',
                    'origin',
                    'org.freenas:refquota_critical',
                    'org.freenas:refquota_warning',
                    'quota',
                    'org.freenas:quota_critical',
                    'org.freenas:quota_warning',
                    'refreservation',
                    'reservation',
                    'mountpoint',
                    'encryption',
                    'encryptionroot',
                    'keyformat',
                    'keystatus',
                    'volsize',
                    'sync',
                    'compression',
                    'dedup',
                ],
                'snapshots_count': True,
            }
        }
        datasets = self.middleware.call_sync('pool.dataset.query', [], options)
        mnt_info = getmntinfo()
        info = self.build_details(mnt_info)
        for dataset in datasets:
            self.collapse_datasets(dataset, info, mnt_info)

        return datasets

    @private
    def normalize_dataset(self, dataset, info, mnt_info):
        atime, case, readonly = self.get_mntinfo(dataset, mnt_info)
        dataset['locked'] = dataset['locked']
        dataset['atime'] = atime
        dataset['casesensitive'] = case
        dataset['readonly'] = readonly
        dataset['thick_provisioned'] = any((dataset['reservation']['value'], dataset['refreservation']['value']))
        dataset['nfs_shares'] = self.get_nfs_shares(dataset, info['nfs'])
        dataset['smb_shares'] = self.get_smb_shares(dataset, info['smb'])
        dataset['iscsi_shares'] = self.get_iscsi_shares(dataset, info['iscsi'])
        dataset['vms'] = self.get_vms(dataset, info['vm'])
        dataset['apps'] = self.get_apps(dataset, info['app'])
        dataset['replication_tasks_count'] = self.get_repl_tasks_count(dataset, info['repl'])
        dataset['snapshot_tasks_count'] = self.get_snapshot_tasks_count(dataset, info['snap'])
        dataset['cloudsync_tasks_count'] = self.get_cloudsync_tasks_count(dataset, info['cloud'])
        dataset['rsync_tasks_count'] = self.get_rsync_tasks_count(dataset, info['rsync'])

    @private
    def collapse_datasets(self, dataset, info, mnt_info):
        self.normalize_dataset(dataset, info, mnt_info)
        for child in dataset.get('children', []):
            self.collapse_datasets(child, info, mnt_info)

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
    def get_mntinfo(self, ds, mntinfo):
        atime = case = True
        readonly = False
        for devid, info in filter(lambda x: x[1]['mountpoint'] == ds['mountpoint'], mntinfo.items()):
            atime = not ('NOATIME' in info['mount_opts'])
            readonly = 'RO' in info['mount_opts']
            case = any((i for i in ('CASESENSITIVE', 'CASEMIXED') if i in info['super_opts']))

        # case sensitivity is either on or off (sensitive or insensitve)
        # the "mixed" property is silently ignored in our use case because it
        # only applies to illumos kernel when using the in-kernel SMB server.
        # if it's set to "mixed" on linux, it's treated as case sensitive.
        return atime, case, readonly

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
        for vm in self.middleware.call_sync('datastore.query', 'vm.device', [['dtype', 'in', ['RAW', 'DISK']]]):
            if vm['dtype'] == 'DISK':
                # disk type is always a zvol
                vm['zvol'] = zvol_path_to_name(vm['attributes']['path'])
            else:
                # raw type is always a file
                vm['mount_info'] = self.get_mount_info(vm['attributes']['path'], mntinfo)

            results['vm'].append(vm)

        # app
        for app_name, paths in self.middleware.call_sync('chart.release.get_consumed_host_paths').items():
            # We want to filter out any other paths which might be consumed to improve performance here
            # and avoid unnecessary mount info calls i.e /proc /sys /etc/ etc
            for path in filter(
                lambda x: x.startswith('/mnt/') and 'ix-applications/' not in x,
                paths
            ):
                results['app'].append({
                    'name': app_name,
                    'path': path,
                    'mount_info': self.get_mount_info(path, mntinfo),
                })

        return results

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
        for share in iscsishares:
            if share['extent']['type'] == 'DISK' and share['extent']['path'].removeprefix('zvol/') == ds['id']:
                # we store extent information prefixed with `zvol/` (i.e. zvol/tank/zvol01).
                iscsi_shares.append({
                    'enabled': share['extent']['enabled'],
                    'type': 'DISK',
                    'path': f'/dev/{share["extent"]["path"]}',
                })
            elif share['extent']['type'] == 'FILE' and share['mount_info'].get('mount_source') == ds['id']:
                # this isn't common but possible, you can share a "file"
                # via iscsi which means it's not a dataset but a file inside
                # a dataset so we need to find the source dataset for the file
                iscsi_shares.append({
                    'enabled': share['extent']['enabled'],
                    'type': 'FILE',
                    'path': share['extent']['path'],
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
        return self._get_push_tasks_count(ds, cldtasks)

    @private
    def get_rsync_tasks_count(self, ds, rsynctasks):
        return self._get_push_tasks_count(ds, rsynctasks)

    def _get_push_tasks_count(self, ds, tasks):
        count = 0
        if ds['mountpoint']:
            for i in filter(lambda x: x['direction'] == 'PUSH', tasks):
                # we only care about cloud sync tasks that are configured to push
                if pathlib.Path(ds['mountpoint']).is_relative_to(i['path']):
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
            if app['path'] == ds['mountpoint'] or app['mount_info'].get('mount_source') == ds['id']:
                apps.append({'name': app['name'], 'path': app['path']})

        return apps
