from middlewared.service import Service
from datetime import datetime

import json
import asyncio
import random
import aiohttp
import hashlib


class UsageService(Service):
    class Config:
        private = True

    async def start(self):
        if (
            await self.middleware.call('system.general.config')
        )['usage_collection']:
            try:
                gather = await self.gather()
                async with aiohttp.ClientSession(
                    raise_for_status=True
                ) as session:
                    await session.post(
                        'https://usage.freenas.org/submit',
                        data=gather,
                        headers={"Content-type": "application/json"}
                    )
            except Exception as e:
                # We still want to schedule the next call
                self.logger.error(e)

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

    async def gather(self):
        network = await self.middleware.call('interfaces.query')

        hardware = await self.gather_hardware(network)
        jails = await self.gather_jails()
        network = await self.gather_network(network)
        system = await self.gather_system()
        plugins = await self.gather_plugins()
        pools = await self.gather_pools()
        services = await self.gather_services()
        sharing = await self.gather_sharing()
        vms = await self.gather_vms()

        return json.dumps(
            {
                **hardware,
                **jails,
                **network,
                **{k: v for l in system['gather_system'] for k, v in l.items()},
                **plugins,
                **pools,
                **services,
                **sharing,
                **vms
            }, sort_keys=True
        )

    async def gather_hardware(self, network):
        info = await self.middleware.call('system.info')

        return {
            'hardware': {
                'cpus': info['cores'],
                'memory': info['physmem'],
                'nics': len(network)
            }
        }

    async def gather_jails(self):
        jails = await self.middleware.call('jail.query')
        jail_list = []

        for j in jails:
            jail_list.append(
                {
                    'nat': bool(j['nat']),
                    'release': j['release'],
                    'vnet': bool(j['vnet'])
                }
            )

        return {'jails': jail_list}

    async def gather_network(self, network):
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
            for l in network:
                if l['type'] == 'LINK_AGGREGATION':
                    lag_list.append(
                        {
                            'members': l['lag_ports'],
                            'mtu': l['mtu'],
                            'type': l['lag_protocol']
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

    async def gather_system(self):
        system = await self.middleware.call('system.info')
        platform = 'FreeNAS' if await self.middleware.call(
            'system.is_freenas'
        ) else 'TrueNAS'

        usage_version = 1
        version = system['version']
        system_hash = hashlib.sha256((await self.middleware.call(
            'systemdataset.config'
        ))['uuid'].encode()).hexdigest()
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
            'gather_system': [
                {'system_hash': system_hash},
                {'platform': platform},
                {'usage_version': usage_version},
                {'version': version},
                {'system': [
                    {
                        'users': users, 'snapshots': snapshots, 'zvols': zvols,
                        'datasets': datasets
                    }
                ]}
            ]
        }

    async def gather_plugins(self):
        return {
            'plugins': [
                {'name': p['name'], 'version': p['version']}
                for p in (await self.middleware.call('plugin.query'))
            ]
        }

    async def gather_pools(self):
        pools = await self.middleware.call('pool.query')
        pool_list = []

        for p in pools:
            if p['status'] == 'OFFLINE':
                continue

            disks = 0
            vdevs = 0
            type = 'STRIPE'

            try:
                pd = (await self.middleware.call(
                    'zfs.dataset.query', [('id', '=', p['name'])],
                    {'get': True}
                ))['properties']
            except IndexError:
                self.logger.error(
                    f'{p["name"]} is missing, skipping collection',
                    exc_info=True
                )

            for d in p['topology']['data']:
                if not d.get('path'):
                    vdevs += 1
                    type = d['type']
                    disks += len(d['children'])
                else:
                    disks += 1

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
                    'usedbyrefreservation':
                        pd['usedbyrefreservation']['parsed'],
                    'vdevs': vdevs if vdevs else disks,
                    'zil': bool(p['topology']['log'])
                }
            )

        return {'pools': pool_list}

    async def gather_services(self):
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

    async def gather_sharing(self):
        services = ['afp', 'iscsi', 'nfs', 'smb', 'webdav']
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
                            'guestonly': s['guestonly'],
                            'abe': s['abe'],
                            'vfsobjects': s['vfsobjects']
                        }
                    )
                elif service == 'afp':
                    sharing_list.append(
                        {
                            'type': service.upper(),
                            'home': s['home'],
                            'timemachine': s['timemachine'],
                            'zerodev': s['nodev'],
                            'nostat': s['nostat'],
                            'unixpriv': s['upriv']
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
                            'legacy': extent['legacy']
                        }
                    )

        for s in services:
            await gather_service(s)

        return {'shares': sharing_list}

    async def gather_vms(self):
        vms = await self.middleware.call('vm.query')
        vm_list = []

        for v in vms:
            nics = 0
            vncs = 0
            disks = 0
            vnc_list = []

            for d in v['devices']:
                dtype = d['dtype']

                if dtype == 'NIC':
                    nics += 1
                elif dtype == 'DISK':
                    disks += 1
                elif dtype == 'VNC':
                    vncs += 1
                    attrs = d['attributes']

                    vnc_list.append(
                        {
                            'wait': attrs['wait'],
                            'vnc_resolution': attrs['vnc_resolution'],
                            'web': attrs['vnc_web']
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
                    'vncs': vncs,
                    'vnc_configs': vnc_list
                }
            )

        return {'vms': vm_list}


async def setup(middleware):
    now = datetime.utcnow()
    event_loop = asyncio.get_event_loop()

    event_loop.call_at(
        random.uniform(1, (
            now.replace(hour=23, minute=59, second=59) - now
        ).total_seconds()),
        lambda: asyncio.ensure_future(
            middleware.call('usage.start')
        )
    )
