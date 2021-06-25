import json
import asyncio
import random
import aiohttp
import os

from copy import deepcopy
from collections import defaultdict
from datetime import datetime

from middlewared.service import Service
from middlewared.utils import osc


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
        now = datetime.utcnow()
        scheduled = (
            now.replace(hour=23, minute=59, second=59) - now
        ).total_seconds() + random.uniform(1, 86400)

        event_loop.call_later(
            scheduled,
            lambda: asyncio.ensure_future(self.middleware.call('usage.start'))
        )
        self.logger.debug(f'Scheduled next run in {round(scheduled)} seconds')

        return True

    async def submit_stats(self, data):
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            await session.post(
                'https://usage.freenas.org/submit',
                data=json.dumps(data, sort_keys=True),
                headers={'Content-type': 'application/json'},
                proxy=os.environ.get('http_proxy'),
            )

    def get_gather_context(self):
        datasets = self.middleware.call_sync('zfs.dataset.query')
        context = {
            'network': self.middleware.call_sync('interface.query'),
            'root_datasets': {},
            'zvols': [],
            'datasets': {},
        }
        for ds in datasets:
            if '/' not in ds['id']:
                context['root_datasets'][ds['id']] = ds
            elif ds['type'] == 'VOLUME':
                context['zvols'].append(ds)
            context['datasets'][ds['id']] = ds
        return context

    def gather(self, restrict_usage=None):
        context = self.get_gather_context()
        restrict_usage = restrict_usage or []

        usage_stats = {}
        for func in filter(
            lambda f: (
                f.startswith('gather_') and callable(getattr(self, f)) and (
                    not f.endswith(('_freebsd', '_linux')) or f.rsplit('_', 1)[-1].upper() == osc.SYSTEM
                ) and (not restrict_usage or f in restrict_usage)
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
        return {
            'total_capacity': sum(
                d['properties']['used']['parsed'] + d['properties']['available']['parsed']
                for d in context['root_datasets'].values()
            )
        }

    def gather_backup_data(self, context):
        backed = {
            'cloudsync': 0,
            'rsynctask': 0,
            'zfs_replication': 0,
            'total_size': 0,
        }
        datasets_data = context['datasets']
        datasets = deepcopy(datasets_data)
        for namespace in ('cloudsync', 'rsynctask'):
            task_datasets = deepcopy(datasets_data)
            for task in self.middleware.call_sync(
                f'{namespace}.query', [['enabled', '=', True], ['direction', '=', 'PUSH'], ['locked', '=', False]]
            ):
                try:
                    task_ds = self.middleware.call_sync('zfs.dataset.path_to_dataset', task['path'])
                except Exception:
                    self.logger.error('Unable to retrieve dataset of path %r', task['path'], exc_info=True)
                    task_ds = None

                if task_ds:
                    task_ds_data = task_datasets.pop(task_ds, None)
                    if task_ds_data:
                        backed[namespace] += task_ds_data['properties']['used']['parsed']
                    ds = datasets.pop(task_ds, None)
                    if ds:
                        backed['total_size'] += ds['properties']['used']['parsed']

        repl_datasets = deepcopy(datasets_data)
        for task in self.middleware.call_sync(
            'replication.query', [['enabled', '=', True], ['transport', '!=', 'LOCAL'], ['direction', '=', 'PUSH']]
        ):
            for source in filter(lambda s: s in repl_datasets, task['source_datasets']):
                r_ds = repl_datasets.pop(source, None)
                if r_ds:
                    backed['zfs_replication'] += r_ds['properties']['used']['parsed']
                ds = datasets.pop(source, None)
                if ds:
                    backed['total_size'] += ds['properties']['used']['parsed']

        return {
            'data_backup_stats': backed,
            'data_without_backup_size': sum([ds['properties']['used']['parsed'] for ds in datasets.values()], start=0)
        }

    def gather_filesystem_usage(self, context):
        return {
            'datasets': {
                'total_size': sum(
                    [d['properties']['used']['parsed'] for d in context['root_datasets'].values()], start=0
                )
            },
            'zvols': {
                'total_size': sum(
                    [d['properties']['used']['parsed'] for d in context['zvols']], start=0
                ),
            },
        }

    async def gather_ha_stats(self, context):
        return {
            'ha_licensed': await self.middleware.call('failover.licensed'),
        }

    async def gather_directory_service_stats(self, context):
        config = await self.middleware.call('ldap.config')
        return {
            'directory_services': {
                'state': await self.middleware.call('directoryservices.get_state'),
                'ldap': {
                    'kerberos_realm_populated': bool(config['kerberos_realm']),
                    'has_samba_schema': config['has_samba_schema'],
                },
            },
        }

    async def gather_cloud_services(self, context):
        return {
            'cloud_services': list({
                t['credentials']['provider']
                for t in await self.middleware.call('cloudsync.query', [['enabled', '=', True]])
            })
        }

    async def gather_hardware(self, context):
        network = context['network']

        return {
            'hardware': {
                'cpus': (await self.middleware.call('system.cpu_info'))['core_count'],
                'memory': (await self.middleware.call('system.mem_info'))['physmem_size'],
                'nics': len(network),
                'disks': [
                    {k: disk[k]} for disk in await self.middleware.call('disk.query') for k in ['model']
                ]
            }
        }

    async def gather_applications_linux(self, context):
        # We want to retrieve following information
        # 1) No of installed chart releases
        # 2) catalog items with versions installed
        # 3) No of backups
        # 4) No of automatic backups taken
        # 5) List of docker images
        # 6) Configured cluster cidr info
        k8s_config = await self.middleware.call('kubernetes.config')
        output = {
            'chart_releases': 0,
            # catalog -> train -> item -> versions
            'catalog_items': defaultdict(
                lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))
            ),
            'chart_releases_backups': {
                'total_backups': 0,
                'automatic_backups': 0,
            },
            'docker_images': set(),
            'kubernetes_config': {
                'cluster_cidr': k8s_config['cluster_cidr'],
                'service_cidr': k8s_config['service_cidr'],
            },
        }
        catalogs = {c['label']: c for c in await self.middleware.call('catalog.query')}
        chart_releases = await self.middleware.call('chart.release.query')
        output['chart_releases'] = len(chart_releases)
        for chart_release in chart_releases:
            chart = chart_release['chart_metadata']
            catalog = catalogs.get(chart_release['catalog'])
            if not catalog:
                # If the catalog was deleted, it's no use trying to log information below as we can't
                # trace back to which item is really installed
                continue
            output['catalog_items'][catalog['repository']][catalog['branch']][
                chart_release['catalog_train']][chart['name']][chart['version']] += 1

        backups = await self.middleware.call('kubernetes.list_backups')
        backup_update_prefix = await self.middleware.call('kubernetes.get_system_update_backup_prefix')
        output['chart_releases_backups'].update({
            'total_backups': len(backups),
            'automatic_backups': len([b for b in backups if b.startswith(backup_update_prefix)]),
        })
        for image in await self.middleware.call('container.image.query'):
            output['docker_images'].update(image['repo_tags'])

        output['docker_images'] = list(output['docker_images'])

        return output

    async def gather_network(self, context):
        network = context['network']

        async def gather_bridges():
            bridge_list = []
            for b in network:
                if b['type'] == 'BRIDGE':
                    bridge_list.append(
                        {
                            'members': b['bridge_members'],
                            'mtu': b['mtu'],
                        }
                    )
            return {'bridges': bridge_list}

        async def gather_lags():
            lag_list = []
            for i in network:
                if i['type'] == 'LINK_AGGREGATION':
                    lag_list.append(
                        {
                            'members': i['lag_ports'],
                            'mtu': i['mtu'],
                            'type': i['lag_protocol']
                        }
                    )
            return {'lags': lag_list}

        async def gather_physical():
            phys_list = []
            for i in network:
                if i['type'] == 'PHYSICAL':
                    phys_list.append(
                        {
                            'name': i['name'],
                            'mtu': i['mtu'],
                            'dhcp': i['ipv4_dhcp'],
                            'slaac': i['ipv6_auto']
                        }
                    )
            return {'phys': phys_list}

        async def gather_vlans():
            vlan_list = []
            for v in network:
                if v['type'] == 'VLAN':
                    vlan_list.append(
                        {
                            'mtu': v['mtu'],
                            'name': v['name'],
                            'tag': v['vlan_tag'],
                            'pcp': v['vlan_pcp']
                        }
                    )
            return {'vlans': vlan_list}

        bridges = await gather_bridges()
        lags = await gather_lags()
        phys = await gather_physical()
        vlans = await gather_vlans()

        return {'network': {**bridges, **lags, **phys, **vlans}}

    async def gather_system_version(self, context):
        return {'version': await self.middleware.call('system.version')}

    async def retrieve_system_hash(self):
        return await self.middleware.call('system.host_id')

    async def gather_system(self, context):
        platform = 'TrueNAS-{}'.format(await self.middleware.call(
            'system.product_type'
        ))

        usage_version = 1
        datasets = await self.middleware.call(
            'zfs.dataset.query', [('type', '!=', 'VOLUME')], {'count': True}
        )
        users = await self.middleware.call(
            'user.query', [], {'count': True}
        )
        snapshots = await self.middleware.call(
            'zfs.snapshot.query', [], {'count': True}
        )
        zvols = await self.middleware.call(
            'zfs.dataset.query', [('type', '=', 'VOLUME')], {'count': True}
        )

        return {
            'system_hash': await self.retrieve_system_hash(),
            'platform': platform,
            'usage_version': usage_version,
            'system': [{'users': users, 'snapshots': snapshots, 'zvols': zvols, 'datasets': datasets}]
        }

    async def gather_plugins_freebsd(self, context):
        try:
            plugins = await self.middleware.call('plugin.query')
        except Exception:
            plugins = []

        return {
            'plugins': [
                {'name': p['plugin'], 'version': p['version']}
                for p in plugins
            ]
        }

    async def gather_pools(self, context):
        pools = await self.middleware.call('pool.query')
        pool_list = []

        for p in pools:
            if p['status'] == 'OFFLINE':
                continue

            disks = 0
            vdevs = 0
            type = 'UNKNOWN'

            pd = context['root_datasets'].get(p['name'])
            if not pd:
                self.logger.error('%r is missing, skipping collection', p['name'])
                continue
            else:
                pd = pd['properties']

            for d in p['topology']['data']:
                if not d.get('path'):
                    vdevs += 1
                    type = d['type']
                    disks += len(d['children'])
                else:
                    disks += 1
                    type = 'STRIPE'

            pool_list.append(
                {
                    'capacity': pd['used']['parsed'] + pd['available']['parsed'],
                    'disks': disks,
                    'encryption': bool(p['encrypt']),
                    'l2arc': bool(p['topology']['cache']),
                    'type': type.lower(),
                    'usedbydataset': pd['usedbydataset']['parsed'],
                    'usedbysnapshots': pd['usedbysnapshots']['parsed'],
                    'usedbychildren': pd['usedbychildren']['parsed'],
                    'usedbyrefreservation': pd['usedbyrefreservation']['parsed'],
                    'vdevs': vdevs if vdevs else disks,
                    'zil': bool(p['topology']['log'])
                }
            )

        return {'pools': pool_list}

    async def gather_services(self, context):
        services = await self.middleware.call('service.query')
        service_list = []

        for s in services:
            service_list.append(
                {
                    'enabled': s['enable'],
                    'name': s['service']
                }
            )

        return {'services': service_list}

    async def gather_sharing(self, context):
        services = ['iscsi', 'nfs', 'smb', 'webdav']
        sharing_list = []

        async def gather_service(service):
            namespace = f'sharing.{service}' if service != 'iscsi' \
                else 'iscsi.targetextent'
            shares = await self.middleware.call(f'{namespace}.query')

            # AUX params wanted?
            for s in shares:
                if service == 'smb':
                    sharing_list.append(
                        {
                            'type': service.upper(),
                            'home': s['home'],
                            'timemachine': s['timemachine'],
                            'browsable': s['browsable'],
                            'recyclebin': s['recyclebin'],
                            'shadowcopy': s['shadowcopy'],
                            'guestok': s['guestok'],
                            'abe': s['abe'],
                            'acl': s['acl'],
                            'fsrvp': s['fsrvp'],
                            'streams': s['streams'],
                        }
                    )
                elif service == 'nfs':
                    sharing_list.append(
                        {
                            'type': service.upper(),
                            'alldirs': s['alldirs'],
                            'readonly': s['ro'],
                            'quiet': s['quiet']
                        }
                    )
                elif service == 'webdav':
                    sharing_list.append(
                        {
                            'type': service.upper(),
                            'readonly': s['ro'],
                            'changeperms': s['perm']
                        }
                    )
                elif service == 'iscsi':
                    target = await self.middleware.call(
                        'iscsi.target.query', [('id', '=', s['target'])],
                        {'get': True}
                    )
                    extent = await self.middleware.call(
                        'iscsi.extent.query', [('id', '=', s['extent'])],
                        {'get': True}
                    )

                    sharing_list.append(
                        {
                            'type': service.upper(),
                            'mode': target['mode'],
                            'groups': target['groups'],
                            'iscsi_type': extent['type'],
                            'filesize': extent['filesize'],
                            'blocksize': extent['blocksize'],
                            'pblocksize': extent['pblocksize'],
                            'avail_threshold': extent['avail_threshold'],
                            'insecure_tpc': extent['insecure_tpc'],
                            'xen': extent['xen'],
                            'rpm': extent['rpm'],
                            'readonly': extent['ro'],
                            'legacy': extent['vendor'] == 'FreeBSD',
                            'vendor': extent['vendor'],
                        }
                    )

        for s in services:
            await gather_service(s)

        return {'shares': sharing_list}

    async def gather_vms(self, context):
        vms = await self.middleware.call('vm.query')
        vm_list = []

        for v in vms:
            nics = 0
            disks = 0
            display_list = []

            for d in v['devices']:
                dtype = d['dtype']

                if dtype == 'NIC':
                    nics += 1
                elif dtype == 'DISK':
                    disks += 1
                elif dtype == 'DISPLAY':
                    attrs = d['attributes']

                    display_list.append(
                        {
                            'wait': attrs.get('wait'),
                            'resolution': attrs.get('resolution'),
                            'web': attrs.get('web')
                        }
                    )

            vm_list.append(
                {
                    'bootloader': v['bootloader'],
                    'memory': v['memory'],
                    'vcpus': v['vcpus'],
                    'autostart': v['autostart'],
                    'time': v['time'],
                    'nics': nics,
                    'disks': disks,
                    'display_devices': len(display_list),
                    'display_devices_configs': display_list
                }
            )

        return {'vms': vm_list}


async def setup(middleware):
    now = datetime.utcnow()
    event_loop = asyncio.get_event_loop()

    await middleware.call('network.general.register_activity', 'usage', 'Anonymous usage statistics')
    event_loop.call_at(
        random.uniform(1, (
            now.replace(hour=23, minute=59, second=59) - now
        ).total_seconds()),
        lambda: asyncio.ensure_future(
            middleware.call('usage.start')
        )
    )
