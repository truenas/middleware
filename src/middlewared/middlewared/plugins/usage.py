import asyncio
import os
import random
from collections import defaultdict

import aiohttp

from middlewared.api.current import ZFSResourceQuery
from middlewared.service import Service
from middlewared.utils.ajson import json
from middlewared.utils.time_utils import utc_now
from middlewared.plugins.zfs_.utils import path_to_dataset_impl

USAGE_URL = 'https://usage.truenas.com/submit'


class UsageService(Service):

    FAILED_RETRIES = 3

    class Config:
        private = True

    async def start(self):
        retries = self.FAILED_RETRIES
        while retries:
            if (
                not await self.middleware.call('failover.is_single_master_node') or not await self.middleware.call(
                    'network.general.can_perform_activity', 'usage'
                )
            ):
                break

            if (await self.middleware.call('system.general.config'))['usage_collection']:
                restrict_usage = []
            else:
                restrict_usage = ['gather_total_capacity', 'gather_system_version']

            try:
                await self.middleware.call(
                    'usage.submit_stats', await self.middleware.call('usage.gather', restrict_usage)
                )
            except Exception as e:
                # We still want to schedule the next call
                self.logger.error(e)
                retries -= 1
                if retries:
                    self.logger.debug('Retrying gathering stats after 30 minutes')
                    await asyncio.sleep(1800)
            else:
                break

        event_loop = asyncio.get_event_loop()
        now = utc_now()
        scheduled = (
            now.replace(hour=23, minute=59, second=59) - now
        ).total_seconds() + random.uniform(1, 86400)

        event_loop.call_later(
            scheduled,
            lambda: self.middleware.create_task(self.middleware.call('usage.start'))
        )
        self.logger.debug(f'Scheduled next run in {round(scheduled)} seconds')

        return True

    async def submit_stats(self, data):
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            await session.post(
                USAGE_URL,
                data=await json.dumps(data, sort_keys=True),
                headers={'Content-type': 'application/json'},
                proxy=os.environ.get('http_proxy'),
            )

    def get_gather_context(self):
        context = {
            'network': self.middleware.call_sync('interface.query'),
            'root_datasets': {},
            'total_capacity': 0,
            'datasets_total_size': 0,
            'datasets_total_size_recursive': 0,
            'zvols_total_size': 0,
            'zvols': [],
            'datasets': {},
            'total_datasets': 0,
            'total_zvols': 0,
            'services': [],
        }
        for i in self.middleware.call_sync('datastore.query', 'services.services', [], {'prefix': 'srv_'}):
            context['services'].append({'name': i['service'], 'enabled': i['enable']})

        qry_ops = ZFSResourceQuery(get_children=True, exclude_internal_paths=False)
        for ds in self.call_sync2(self.s.zfs.resource.query_impl, qry_ops):
            if ds['name'] == ds['pool']:
                context['root_datasets'][ds['pool']] = ds
                context['total_datasets'] += 1
                context['datasets_total_size'] += ds['properties']['used']['value']
                context['total_capacity'] += (
                    ds['properties']['used']['value'] + ds['properties']['available']['value']
                )
            elif ds['type'] == 'VOLUME':
                context['zvols'].append(ds)
                context['total_zvols'] += 1
                context['zvols_total_size'] += ds['properties']['used']['value']
            elif ds['type'] == 'FILESYSTEM':
                context['total_datasets'] += 1

            context['datasets_total_size_recursive'] += ds['properties']['used']['value']
            context['datasets'][ds['name']] = ds

        return context

    def gather(self, restrict_usage=None):
        context = self.get_gather_context()
        restrict_usage = restrict_usage or []

        usage_stats = {}
        for func in filter(
            lambda f: (
                f.startswith('gather_') and callable(getattr(self, f)) and (not restrict_usage or f in restrict_usage)
            ),
            dir(self)
        ):
            try:
                stats = self.middleware.call_sync(f'usage.{func}', context)
            except Exception as e:
                self.logger.error('Failed to gather stats from %r: %s', func, e, exc_info=True)
            else:
                usage_stats.update(stats)

        return usage_stats

    def gather_total_capacity(self, context):
        return {'total_capacity': context['total_capacity']}

    def gather_backup_data(self, context):
        backed = {'cloudsync': 0, 'rsynctask': 0, 'zfs_replication': 0, 'total_size': 0}
        filters = [['enabled', '=', True], ['direction', '=', 'PUSH'], ['locked', '=', False]]
        tasks_found = {'cloudsync': set(), 'rsynctask': set()}
        for namespace in ('cloudsync', 'rsynctask'):
            opposite_namespace = 'rsynctask' if namespace == 'cloudsync' else 'cloudsync'
            for task in self.middleware.call_sync(f'{namespace}.query', filters):
                try:
                    task_ds = path_to_dataset_impl(task['path'])
                except Exception:
                    self.logger.error('Failed mapping path %r to dataset', task['path'], exc_info=True)
                else:
                    if (task_ds and task_ds in context['datasets']) and (task_ds not in tasks_found[namespace]):
                        # dataset for the task was found, and exists and hasn't already been calculated
                        size = context['datasets'][task_ds]['properties']['used']['value']
                        backed[namespace] += size
                        if task_ds not in tasks_found[opposite_namespace]:
                            # a "task" (cloudsync, rsync, replication) can be backing up the same dataset
                            # so we don't want to add to the total backed up size because it will report
                            # an inflated number. Instead we only add to the total backed up size when it's
                            # a dataset only being backed up by a singular cloud/rsync/replication task
                            backed['total_size'] += size

                        tasks_found[namespace].add(task_ds)

        repls_found = set()
        filters = [['enabled', '=', True], ['transport', '!=', 'LOCAL'], ['direction', '=', 'PUSH']]
        for task in self.middleware.call_sync('replication.query', filters):
            for source in filter(lambda s: s in context['datasets'] and s not in repls_found, task['source_datasets']):
                size = context['datasets'][source]['properties']['used']['value']
                backed['zfs_replication'] += size
                repls_found.add(source)
                if source not in tasks_found['cloudsync'] and source not in tasks_found['rsynctask']:
                    # a "task" (cloudsync, rsync, replication) can be backing up the same dataset
                    # so we don't want to add to the total backed up size because it will report
                    # an inflated number. Instead we only add to the total backed up size when it's
                    # a dataset only being backed up by a singular cloud/rsync/replication task
                    backed['total_size'] += size

        return {
            'data_backup_stats': backed,
            'data_without_backup_size': context['datasets_total_size_recursive'] - backed['total_size']
        }

    async def gather_applications(self, context):
        # We want to retrieve following information
        # 1) No of installed apps
        # 2) catalog items with versions installed
        # 3) List of docker images
        output = {
            'apps': 0,
            # train -> item -> versions
            'catalog_items': defaultdict(lambda: defaultdict(lambda: defaultdict(int))),
            'docker_images': set(),
        }
        apps = await self.middleware.call('app.query')
        output['apps'] = len(apps)
        for app in apps:
            app_metadata = app['metadata']
            output['catalog_items'][app_metadata['train']][app_metadata['name']][app['version']] += 1

        for image in await self.middleware.call('app.image.query'):
            output['docker_images'].update(image['repo_tags'])

        output['docker_images'] = list(output['docker_images'])
        return output

    def gather_filesystem_usage(self, context):
        return {
            'datasets': {'total_size': context['datasets_total_size']},
            'zvols': {'total_size': context['zvols_total_size']},
        }

    async def gather_ha_stats(self, context):
        return {
            'ha_licensed': await self.middleware.call('failover.licensed'),
        }

    async def gather_directory_service_stats(self, context):
        status = await self.middleware.call('directoryservices.status')
        return {'directory_services': status}

    async def gather_cloud_services(self, context):
        return {
            'cloud_services': list({
                t['credentials']['provider']['type']
                for t in await self.middleware.call(
                    'cloudsync.query', [['enabled', '=', True]], {'select': ['enabled', 'credentials']}
                )
            })
        }

    async def gather_hardware(self, context):
        network = context['network']
        cpu = await self.middleware.call('system.cpu_info')

        return {
            'hardware': {
                'cpus': cpu['core_count'],
                'cpu_model': cpu['cpu_model'],
                'memory': (await self.middleware.call('system.mem_info'))['physmem_size'],
                'nics': len(network),
                'disks': [
                    {k: disk[k]} for disk in await self.middleware.call('disk.query') for k in ['model']
                ]
            }
        }

    async def gather_method_stats(self, context):
        return {
            'method_stats': self.middleware.external_method_calls,
        }

    async def gather_network(self, context):
        info = {'network': {'bridges': [], 'lags': [], 'phys': [], 'vlans': []}}
        for i in context['network']:
            if i['type'] == 'BRIDGE':
                info['network']['bridges'].append({'members': i['bridge_members'], 'mtu': i['mtu']})
            elif i['type'] == 'LINK_AGGREGATION':
                info['network']['lags'].append({'members': i['lag_ports'], 'mtu': i['mtu'], 'type': i['lag_protocol']})
            elif i['type'] == 'PHYSICAL':
                info['network']['phys'].append({
                    'name': i['name'], 'mtu': i['mtu'], 'dhcp': i['ipv4_dhcp'], 'slaac': i['ipv6_auto']
                })
            elif i['type'] == 'VLAN':
                info['network']['vlans'].append({
                    'mtu': i['mtu'], 'name': i['name'], 'tag': i['vlan_tag'], 'pcp': i['vlan_pcp']
                })

        return info

    async def gather_system_version(self, context):
        return {
            'platform': f'TrueNAS-{await self.middleware.call("system.product_type")}',
            'version': await self.middleware.call('system.version'),
            'is_vendored': await self.middleware.call('system.vendor.is_vendored'),
            'vendor_name': await self.middleware.call('system.vendor.name'),
            'is_virtualized': await self.middleware.call('hardware.virtualization.is_virtualized'),
            'hypervisor': await self.middleware.call('hardware.virtualization.variant'),
        }

    async def gather_system(self, context):
        return {
            'system_hash': await self.middleware.call('system.host_id'),
            'usage_version': 1,
            'system': [{
                'users': await self.middleware.call('user.query', [['local', '=', True]], {'count': True}),
                'zvols': context['total_zvols'],
                'datasets': context['total_datasets'],
            }]
        }

    async def gather_pools(self, context):
        total_raw_capacity = 0  # zpool list -p -o size summed together of all zpools
        pool_list = []
        for p in filter(lambda x: x['status'] != 'OFFLINE', await self.middleware.call('pool.query')):
            total_raw_capacity += p['size']
            disks = vdevs = 0
            _type = 'UNKNOWN'
            if (pd := context['root_datasets'].get(p['name'])) is None:
                self.logger.error('%r is missing, skipping collection', p['name'])
                continue
            else:
                pd = pd['properties']

            for d in p['topology']['data']:
                if not d.get('path'):
                    vdevs += 1
                    _type = d['type']
                    disks += len(d['children'])
                else:
                    disks += 1
                    _type = 'STRIPE'

            pool_list.append({
                'capacity': pd['used']['value'] + pd['available']['value'],
                'disks': disks,
                'l2arc': bool(p['topology']['cache']),
                'type': _type.lower(),
                'usedbydataset': pd['usedbydataset']['value'],
                'usedbysnapshots': pd['usedbysnapshots']['value'],
                'usedbychildren': pd['usedbychildren']['value'],
                'usedbyrefreservation': pd['usedbyrefreservation']['value'],
                'vdevs': vdevs if vdevs else disks,
                'zil': bool(p['topology']['log'])
            })

        return {'pools': pool_list, 'total_raw_capacity': total_raw_capacity}

    async def gather_services(self, context):
        return {'services': context['services']}

    async def gather_nfs(self, context_unused):
        num_clients = await self.middleware.call('nfs.client_count')
        nfs_config = await self.middleware.call('nfs.config')
        return {
            'NFS': {
                'enabled_protocols': nfs_config['protocols'],
                'kerberos': nfs_config['v4_krb_enabled'],
                'num_clients': num_clients,
            }
        }

    async def gather_ftp(self, context_unused):
        """ Gather number of FTP connection info """
        ftp_config = await self.middleware.call('ftp.config')
        num_conn = await self.middleware.call('ftp.connection_count')

        return {
            'FTP': {
                'connections_allowed': ftp_config['clients'] * ftp_config['ipconnections'],
                'num_connections': num_conn
            }
        }

    async def gather_sharing(self, context):
        sharing_list = []
        for service in {'iscsi', 'nfs', 'smb'}:
            service_upper = service.upper()
            namespace = f'sharing.{service}' if service != 'iscsi' else 'iscsi.targetextent'
            for s in await self.middleware.call(f'{namespace}.query'):
                if service == 'smb':
                    sharing_list.append({'type': service_upper, 'purpose': s['purpose']})
                elif service == 'nfs':
                    sharing_list.append({'type': service_upper, 'readonly': s['ro']})
                elif service == 'iscsi':
                    tar = await self.middleware.call('iscsi.target.query', [('id', '=', s['target'])], {'get': True})
                    ext = await self.middleware.call(
                        'iscsi.extent.query', [('id', '=', s['extent'])], {
                            'get': True,
                            'extra': {'retrieve_locked_info': False},
                        }
                    )
                    sharing_list.append({
                        'type': service_upper,
                        'mode': tar['mode'],
                        'groups': tar['groups'],
                        'iscsi_type': ext['type'],
                        'filesize': ext['filesize'],
                        'blocksize': ext['blocksize'],
                        'pblocksize': ext['pblocksize'],
                        'avail_threshold': ext['avail_threshold'],
                        'insecure_tpc': ext['insecure_tpc'],
                        'xen': ext['xen'],
                        'rpm': ext['rpm'],
                        'readonly': ext['ro'],
                        'legacy': ext['vendor'] == 'FreeBSD',
                        'vendor': ext['vendor'],
                    })

        return {'shares': sharing_list}

    async def gather_vms(self, context):
        vms = []
        for v in await self.middleware.call('vm.query'):
            nics = disks = 0
            display_list = []
            for d in v['devices']:
                dtype = d['attributes']['dtype']
                if dtype == 'NIC':
                    nics += 1
                elif dtype == 'DISK':
                    disks += 1
                elif dtype == 'DISPLAY':
                    attrs = d['attributes']
                    display_list.append({
                        'wait': attrs.get('wait'),
                        'resolution': attrs.get('resolution'),
                        'web': attrs.get('web')
                    })

            vms.append({
                'bootloader': v['bootloader'],
                'memory': v['memory'],
                'vcpus': v['vcpus'],
                'autostart': v['autostart'],
                'time': v['time'],
                'nics': nics,
                'disks': disks,
                'display_devices': len(display_list),
                'display_devices_configs': display_list
            })

        return {'vms': vms}


async def setup(middleware):
    now = utc_now()
    event_loop = asyncio.get_event_loop()

    await middleware.call('network.general.register_activity', 'usage', 'Anonymous usage statistics')
    event_loop.call_at(
        random.uniform(1, (
            now.replace(hour=23, minute=59, second=59) - now
        ).total_seconds()),
        lambda: middleware.create_task(middleware.call('usage.start'))
    )
