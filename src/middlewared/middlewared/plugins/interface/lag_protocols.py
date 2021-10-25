from middlewared.service import Service


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    async def lag_supported_protocols(self):
        return ['LACP', 'FAILOVER', 'LOADBALANCE']
