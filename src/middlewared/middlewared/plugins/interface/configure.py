from middlewared.service import private, Service


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    async def get_configured_interfaces(self):
        """
        Return a list of configured interfaces.

        This will include names of regular interfaces that have been configured,
        plus any higher-order interfaces and their constituents."""
        ds = await self.middleware.call('interface.get_datastores')
        # Interfaces
        result = set([i['int_interface'] for i in ds['interfaces']])
        # Bridges
        for bridge in ds['bridge']:
            result.update(bridge['members'])
        # VLAN
        for vlan in ds['vlan']:
            result.add(vlan['vlan_pint'])
        # Link Aggregation
        for lag in ds['laggmembers']:
            result.add(lag['lagg_physnic'])
        return list(result)
