from middlewared.service import Service, no_authz_required, private


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    @no_authz_required
    async def lag_supported_protocols(self):
        return ['LACP', 'FAILOVER', 'LOADBALANCE']
