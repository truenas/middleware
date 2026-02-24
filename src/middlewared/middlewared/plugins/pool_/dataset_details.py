from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

from middlewared.plugins.nvmet.constants import NAMESPACE_DEVICE_TYPE
from middlewared.plugins.zfs_.utils import zvol_path_to_name, TNUserProp
from middlewared.utils.mount import statmount

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


def details_impl(ctx: ServiceContext) -> list[dict]:
    """
    Retrieve all dataset(s) details outlining any
    services/tasks which might be consuming them.
    """
    # Build filters and options
    options = {
        'extra': {
            'retrieve_user_props': True,
            'flat': True,
            'order_by': 'name',
            'properties': [
                'atime',
                'casesensitivity',
                'readonly',
                'used',
                'available',
                'usedbysnapshots',
                'usedbydataset',
                'usedbychildren',
                'refquota',
                'origin',
                TNUserProp.REFQUOTA_CRIT.value,
                TNUserProp.REFQUOTA_WARN.value,
                'quota',
                TNUserProp.QUOTA_CRIT.value,
                TNUserProp.QUOTA_WARN.value,
                'refreservation',
                'reservation',
                'mountpoint',
                'mounted',
                'encryption',
                'encryptionroot',
                'keyformat',
                'keystatus',
                'volsize',
                'sync',
                'compression',
                'compressratio',
                'dedup',
            ],
            'snapshots_count': True,
        }
    }

    datasets = ctx.middleware.call_sync('pool.dataset.query', [], options)
    info = build_details(ctx)
    for dataset in datasets:
        collapse_datasets(ctx, dataset, info)

    return datasets


def build_details(ctx: ServiceContext) -> dict[str, list]:
    """Build aggregated information about shares, tasks, and VMs/containers."""
    results = {
        'iscsi': [], 'nfs': [], 'nvmet': [], 'smb': [], 'webshare': [],
        'repl': [], 'snap': [], 'cloud': [],
        'rsync': [], 'vm': [], 'app': [], 'container': [],
    }

    # iscsi
    t_to_e = ctx.middleware.call_sync('iscsi.targetextent.query')
    t = {i['id']: i for i in ctx.middleware.call_sync('iscsi.target.query')}
    e = {i['id']: i for i in ctx.middleware.call_sync('iscsi.extent.query')}
    for i in filter(lambda x: x['target'] in t and t[x['target']]['groups'] and x['extent'] in e, t_to_e):
        results['iscsi'].append({
            'extent': e[i['extent']],
            'target': t[i['target']],
            'mount_info': get_mount_info(e[i['extent']]['path']),
        })

    # nfs, smb and webshare
    for key in ('nfs', 'smb', 'webshare'):
        for share in ctx.middleware.call_sync(f'sharing.{key}.query'):
            share['mount_info'] = get_mount_info(share['path'])
            results[key].append(share)

    # nvmet
    for ns in ctx.middleware.call_sync('nvmet.namespace.query'):
        results['nvmet'].append({
            'namespace': ns,
            'mount_info': get_mount_info(ns['device_path']),
        })

    # replication
    options = {'prefix': 'repl_'}
    for task in ctx.middleware.call_sync('datastore.query', 'storage.replication', [], options):
        results['repl'].append(task)

    # snapshots
    for task in ctx.middleware.call_sync('datastore.query', 'storage.task', [], {'prefix': 'task_'}):
        results['snap'].append(task)

    # cloud sync
    for task in ctx.middleware.call_sync('datastore.query', 'tasks.cloudsync'):
        task['mount_info'] = get_mount_info(task['path'])
        results['cloud'].append(task)

    # rsync
    for task in ctx.middleware.call_sync('rsynctask.query'):
        task['mount_info'] = get_mount_info(task['path'])
        results['rsync'].append(task)

    # vm
    vms = {vm['id']: vm for vm in ctx.middleware.call_sync('datastore.query', 'vm.vm')}
    for vm_device in ctx.middleware.call_sync('vm.device.query', [['attributes.dtype', 'in', ['RAW', 'DISK']]]):
        results['vm'].append(vm_device | parse_virtualization_device_info(vm_device) | {
            'vm_name': vms[vm_device['vm']]['name'],
        })

    # containers
    containers = {
        container['id']: container
        for container in ctx.middleware.call_sync('datastore.query', 'container.container')
    }
    for container_dev in ctx.middleware.call_sync(
        'container.device.query', [['attributes.dtype', 'in', ['RAW', 'DISK', 'FILESYSTEM']]]
    ):
        results['container'].append(
            container_dev | parse_virtualization_device_info(container_dev) | {
                'container_name': containers[container_dev['container']]['name'],
            }
        )

    # apps
    for app in ctx.middleware.call_sync('app.query'):
        for path_config in filter(
            lambda p: p.get('source', '').startswith('/mnt/') and not p['source'].startswith('/mnt/.ix-'),
            app['active_workloads']['volumes']
        ):
            results['app'].append({
                'name': app['name'],
                'path': path_config['source'],
                'mount_info': get_mount_info(path_config['source']),
            })

    return results


def get_mount_info(path: str) -> dict:
    """Get mount information for a given path."""
    if path.startswith('zvol/'):
        return {}

    try:
        mount_info = statmount(path=path)
    except Exception:
        # path deleted/umounted/locked etc
        mount_info = {}

    return mount_info


def parse_virtualization_device_info(dev_: dict) -> dict:
    """Parse VM/container device information to extract zvol or mount info."""
    info = {}
    if dev_['attributes']['dtype'] == 'DISK':
        # disk type is always a zvol
        info['zvol'] = zvol_path_to_name(dev_['attributes']['path'])
    elif dev_['attributes']['dtype'] == 'RAW':
        # raw type is always a file
        info['mount_info'] = get_mount_info(dev_['attributes']['path'])
    else:
        # filesystem type is always a directory
        info['mount_info'] = get_mount_info(dev_['attributes']['source'])
    return info


def normalize_dataset(ctx: ServiceContext, dataset: dict, info: dict) -> None:
    """Normalize dataset by adding share and task information."""
    dataset['thick_provisioned'] = any((dataset['reservation']['value'], dataset['refreservation']['value']))
    dataset['nfs_shares'] = get_nfs_shares(dataset, info['nfs'])
    dataset['smb_shares'] = get_smb_shares(dataset, info['smb'])
    dataset['webshare_shares'] = get_webshare_shares(dataset, info['webshare'])
    dataset['iscsi_shares'] = get_iscsi_shares(dataset, info['iscsi'])
    dataset['nvmet_shares'] = get_nvmet_shares(dataset, info['nvmet'])
    dataset['vms'] = get_vms(dataset, info['vm'])
    dataset['containers'] = get_containers(dataset, info['container'])
    dataset['apps'] = get_apps(dataset, info['app'])
    dataset['replication_tasks_count'] = get_repl_tasks_count(dataset, info['repl'])
    dataset['snapshot_tasks_count'] = get_snapshot_tasks_count(dataset, info['snap'])
    dataset['cloudsync_tasks_count'] = get_cloudsync_tasks_count(dataset, info['cloud'])
    dataset['rsync_tasks_count'] = get_rsync_tasks_count(dataset, info['rsync'])


def collapse_datasets(ctx: ServiceContext, dataset: dict, info: dict) -> None:
    """Recursively normalize dataset and its children."""
    normalize_dataset(ctx, dataset, info)
    for child in dataset.get('children', []):
        collapse_datasets(ctx, child, info)


def get_nfs_shares(ds: dict, nfsshares: list) -> list[dict]:
    """Get NFS shares for a dataset."""
    nfs_shares = []
    for share in nfsshares:
        if share['path'] == ds['mountpoint'] or share['mount_info'].get('mount_source') == ds['id']:
            nfs_shares.append({'enabled': share['enabled'], 'path': share['path']})
    return nfs_shares


def get_smb_shares(ds: dict, smbshares: list) -> list[dict]:
    """Get SMB shares for a dataset."""
    smb_shares = []
    for share in smbshares:
        if share['path'] == ds['mountpoint'] or share['mount_info'].get('mount_source') == ds['id']:
            smb_shares.append({
                'enabled': share['enabled'],
                'path': share['path'],
                'share_name': share['name']
            })
    return smb_shares


def get_iscsi_shares(ds: dict, iscsishares: list) -> list[dict]:
    """Get iSCSI shares for a dataset."""
    iscsi_shares = []
    for share in iscsishares:
        if share['extent']['type'] == 'DISK' and ds['type'] == 'VOLUME':
            if zvol_path_to_name(f"/dev/{share['extent']['path']}") == ds['id']:
                iscsi_shares.append({
                    'enabled': share['extent']['enabled'],
                    'type': 'DISK',
                    'path': f'/dev/{share["extent"]["path"]}',
                })
        elif share['extent']['type'] == 'FILE' and ds['type'] == 'FILESYSTEM':
            if share['mount_info'].get('mount_source') == ds['id']:
                iscsi_shares.append({
                    'enabled': share['extent']['enabled'],
                    'type': 'FILE',
                    'path': share['extent']['path'],
                })
    return iscsi_shares


def get_webshare_shares(ds: dict, webshareshares: list) -> list[dict]:
    """Get webshare shares for a dataset."""
    webshare_shares = []
    for share in webshareshares:
        if share['path'] == ds['mountpoint'] or share['mount_info'].get('mount_source') == ds['id']:
            webshare_shares.append({
                'enabled': share['enabled'],
                'path': share['path'],
                'share_name': share['name']
            })
    return webshare_shares


def get_nvmet_shares(ds: dict, nvmetshares: list) -> list[dict]:
    """Get NVMet shares for a dataset."""
    nvmet_shares = []
    for share in nvmetshares:
        if share['namespace']['device_type'] == NAMESPACE_DEVICE_TYPE.ZVOL.api and ds['type'] == 'VOLUME':
            if zvol_path_to_name(f"/dev/{share['namespace']['device_path']}") == ds['id']:
                nvmet_shares.append({
                    'enabled': share['namespace']['enabled'],
                    'type': 'ZVOL',
                    'path': f'/dev/{share["namespace"]["device_path"]}',
                })
        elif share['namespace']['device_type'] == NAMESPACE_DEVICE_TYPE.FILE.api and ds['type'] == 'FILESYSTEM':
            if share['mount_info'].get('mount_source') == ds['id']:
                nvmet_shares.append({
                    'enabled': share['namespace']['enabled'],
                    'type': 'FILE',
                    'path': share['namespace']['device_path'],
                })
    return nvmet_shares


def get_repl_tasks_count(ds: dict, repltasks: list) -> int:
    """Get count of replication tasks for a dataset."""
    count = 0
    for repl in filter(lambda x: x['direction'] == 'PUSH', repltasks):
        for src_ds in filter(lambda x: x == ds['id'], repl['source_datasets']):
            count += 1
    return count


def get_snapshot_tasks_count(ds: dict, snaptasks: list) -> int:
    """Get count of snapshot tasks for a dataset."""
    return len([i for i in snaptasks if i['dataset'] == ds['id']])


def get_cloudsync_tasks_count(ds: dict, cldtasks: list) -> int:
    """Get count of cloud sync tasks for a dataset."""
    return get_push_tasks_count(ds, cldtasks)


def get_rsync_tasks_count(ds: dict, rsynctasks: list) -> int:
    """Get count of rsync tasks for a dataset."""
    return get_push_tasks_count(ds, rsynctasks)


def get_push_tasks_count(ds: dict, tasks: list) -> int:
    """Get count of push tasks (cloud sync or rsync) for a dataset."""
    count = 0
    if ds['mountpoint']:
        for i in filter(lambda x: x['direction'] == 'PUSH', tasks):
            if pathlib.Path(ds['mountpoint']).is_relative_to(i['path']):
                count += 1
    return count


def get_vms(ds: dict, _vms: list) -> list[dict]:
    """Get VMs using this dataset."""
    vms = []
    for i in _vms:
        if (
            'zvol' in i and i['zvol'] == ds['id'] or
            i['attributes']['path'] == ds['mountpoint'] or
            i.get('mount_info', {}).get('mount_source') == ds['id']
        ):
            vms.append({'name': i['vm_name'], 'path': i['attributes']['path']})
    return vms


def get_containers(ds: dict, _containers: list) -> list[dict]:
    """Get containers using this dataset."""
    containers = []
    for i in _containers:
        path_in_use = i['attributes'].get('path') or i['attributes']['source']
        if (
            'zvol' in i and i['zvol'] == ds['id'] or
            path_in_use == ds['mountpoint'] or
            i.get('mount_info', {}).get('mount_source') == ds['id']
        ):
            containers.append(
                {'name': i['container_name'], 'path': path_in_use}
            )
    return containers


def get_apps(ds: dict, _apps: list) -> list[dict]:
    """Get apps using this dataset."""
    apps = []
    for app in _apps:
        if app['path'] == ds['mountpoint'] or app['mount_info'].get('mount_source') == ds['id']:
            apps.append({'name': app['name'], 'path': app['path']})
    return apps
