from collections import defaultdict

from middlewared.service import Service
from middlewared.schema import Dict, List, IPAddr, returns, accepts


class NetworkGeneralService(Service):

    class Config:
        namespace = 'network.general'
        cli_namespace = 'network.general'

    @accepts()
    @returns(
        Dict(
            'network_summary',
            Dict('ips', additional_attrs=True, required=True),
            List('default_routes', items=[IPAddr('default_route')], required=True),
            List('nameservers', items=[IPAddr('nameserver')], required=True),
        )
    )
    async def summary(self):
        """
        Retrieve general information for current Network.

        Returns a dictionary. For example:

        .. examples(websocket)::

            :::javascript
            {
                "ips": {
                    "vtnet0": {
                        "IPV4": [
                            "192.168.0.15/24"
                        ]
                    }
                },
                "default_routes": [
                    "192.168.0.1"
                ],
                "nameservers": [
                    "192.168.0.1"
                ]
            }
        """
        ips = defaultdict(lambda: defaultdict(list))
        for iface in await self.middleware.call('interface.query'):
            for alias in iface['state']['aliases']:
                if alias['type'] == 'INET':
                    key = 'IPV4'
                elif alias['type'] == 'INET6':
                    key = 'IPV6'
                else:
                    continue
                ips[iface['name']][key].append(f'{alias["address"]}/{alias["netmask"]}')

        default_routes = []
        for route in await self.middleware.call('route.system_routes', [('netmask', 'in', ['0.0.0.0', '::'])]):
            # IPv6 have local addresses that don't have gateways. Make sure we only return a gateway
            # if there is one.
            if route['gateway']:
                default_routes.append(route['gateway'])

        nameservers = []
        for ns in await self.middleware.call('dns.query'):
            nameservers.append(ns['nameserver'])

        return {
            'ips': ips,
            'default_routes': default_routes,
            'nameservers': nameservers,
        }
