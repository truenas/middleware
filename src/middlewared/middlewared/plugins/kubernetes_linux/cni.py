import asyncio
import ipaddress
import subprocess
import time

from middlewared.plugins.interface.netif import netif
from middlewared.service import CallError, ConfigService

from .k8s import api_client, service_accounts


class KubernetesCNIService(ConfigService):

    class Config:
        private = True
        namespace = 'k8s.cni'

    async def config(self):
        return {
            'multus': {'service_account': 'multus'},
            'kube_router': {'service_account': 'kube-router'},
        }

    async def setup_cni(self):
        kube_config = await self.middleware.call('datastore.query', 'services.kubernetes', [], {'get': True})
        config = await self.config()
        async with api_client() as (api, context):
            cni_config = kube_config['cni_config']
            for cni in config:
                if not await self.validate_cni_integrity(cni, kube_config):
                    cni_config[cni] = await service_accounts.get_service_account_details(
                        context['core_api'], config[cni]['service_account']
                    )

        await self.middleware.call(
            'datastore.update', 'services.kubernetes', kube_config['id'], {'cni_config': cni_config}
        )
        await self.middleware.call('etc.generate', 'cni')
        await self.middleware.call('service.start', 'kuberouter')

        rt = netif.RoutingTable()
        timeout = 60
        while timeout > 0:
            if 'kube-router' not in rt.routing_tables:
                await asyncio.sleep(2)
                timeout -= 2
            else:
                break

        if 'kube-router' not in rt.routing_tables:
            raise CallError('Unable to locate kube-router routing table. Please refer to kuberouter logs.')

        await self.middleware.call('k8s.cni.add_user_route_to_kube_router_table')

    async def validate_cni_integrity(self, cni, config=None):
        config = config or await self.middleware.call('datastore.query', 'services.kubernetes', [], {'get': True})
        return all(k in (config['cni_config'].get(cni) or {}) for k in ('ca', 'token'))

    async def kube_router_config(self):
        config = await self.middleware.call('kubernetes.config')
        return {
            'cniVersion': '0.3.0',
            'name': 'ix-net',
            'plugins': [
                {
                    'bridge': 'kube-bridge',
                    'ipam': {
                        'subnet': config['cluster_cidr'],
                        'type': 'host-local',
                    },
                    'isDefaultGateway': True,
                    'name': 'kubernetes',
                    'type': 'bridge',
                },
                {
                    'capabilities': {
                        'portMappings': True,
                        'snat': True,
                    },
                    'type': 'portmap',
                },
            ]
        }

    def add_routes_to_kube_router_table(self):
        rt = netif.RoutingTable()
        kube_router_table = rt.routing_tables['kube-router']
        cluster_cidr = ipaddress.ip_network(self.middleware.call_sync('kubernetes.config')['cluster_cidr'], False)

        while not any(
            r.interface == 'kube-bridge' and str(r.network) == str(cluster_cidr.network_address)
            for r in rt.routes_internal(table_filter=254)
        ):
            time.sleep(5)

        for route in filter(lambda r: (r.interface or '') == 'kube-bridge', rt.routes_internal(table_filter=254)):
            route.table_id = kube_router_table.table_id
            if route in kube_router_table.routes:
                continue
            rt.add(route)

    def add_user_route_to_kube_router_table(self):
        # User route is a default route for kube router table which is going to be
        # used for traffic going outside k8s cluster via pods
        config = self.middleware.call_sync('kubernetes.config')
        if all(not config[k] for k in config if k.startswith('route_v')):
            return

        rt = netif.RoutingTable()
        kube_router_table = rt.routing_tables['kube-router']
        for k in filter(lambda k: config[f'{k}_gateway'] and config[f'{k}_interface'], ('route_v4', 'route_v6')):
            factory = ipaddress.IPv4Address if k.endswith('v4') else ipaddress.IPv6Address
            rt.add(netif.Route(
                factory(0), factory(0), ipaddress.ip_address(config[f'{k}_gateway']), config[f'{k}_interface'],
                table_id=kube_router_table.table_id,
            ))

    def cleanup_cni(self):
        # We want to remove all CNI related configuration when k8s stops
        # We will clean configuration done by kube-router now
        # Below command will cleanup iptables rules and other ipvs bits changed by kube-router
        cp = subprocess.Popen(['kube-router', '--cleanup-config'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        stderr = cp.communicate()[1]
        if cp.returncode:
            raise CallError(f'Failed to cleanup kube-router configuration: {stderr.decode()}')

        tables = netif.RoutingTable().routing_tables
        for t_name in filter(lambda t: t in tables, ('kube-router', 'kube-router-dsr')):
            table = tables[t_name]
            table.flush_routes()
            table.flush_rules()

        interfaces = netif.list_interfaces()
        for iface in map(lambda n: interfaces[n], filter(lambda n: n in interfaces, ('kube-bridge', 'kube-dummy-if'))):
            self.middleware.call_sync('interface.unconfigure', iface, [], [])
