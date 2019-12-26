from middlewared.service import private, ServicePartBase


class InterfaceLagBase(ServicePartBase):
    @private
    async def lag_supported_protocols(self):
        return ['LACP', 'FAILOVER', 'LOADBALANCE']
