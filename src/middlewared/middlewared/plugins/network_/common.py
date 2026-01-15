from middlewared.service import Service

# Used by network.configuration
DEFAULT_NETWORK_DOMAIN = 'local'


class NetworkCommonService(Service):

    class Config:
        namespace = 'network.common'
        private = True

    async def check_failover_disabled(self, schema, verrors):
        if not await self.middleware.call('failover.licensed'):
            return
        elif await self.middleware.call('failover.status') == 'SINGLE':
            return
        elif not (await self.middleware.call('failover.config'))['disabled']:
            verrors.add(schema, 'Failover must be disabled.')

    async def check_dhcp_or_aliases(self, schema, verrors):
        keys = ('ipv4_dhcp', 'ipv6_auto', 'aliases')
        if not any([i[key] for key in keys] for i in await self.middleware.call('interface.query')):
            verrors.add(
                schema, 'At least one interface must be configured with IPv4 DHCP, IPv6 Autoconfig or a static IP.'
            )
