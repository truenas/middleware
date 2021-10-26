from middlewared.service import private, Service


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    async def lag_supported_protocols(self):
        return ['LACP', 'FAILOVER', 'LOADBALANCE']
