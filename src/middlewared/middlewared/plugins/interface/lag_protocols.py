from middlewared.service import no_authz_required, private, Service


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    @no_authz_required
    async def lag_supported_protocols(self):
        return ['LACP', 'FAILOVER', 'LOADBALANCE']
