from middlewared.service import private, ServicePartBase


class InterfaceLaggBase(ServicePartBase):
    @private
    async def lagg_supported_protocols(self):
        return ['LACP', 'FAILOVER', 'LOADBALANCE']
