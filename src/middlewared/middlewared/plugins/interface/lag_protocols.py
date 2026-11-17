from middlewared.api import api_method
from middlewared.api.current import InterfaceLagSupportedProtocolsArgs, InterfaceLagSupportedProtocolsResult
from middlewared.service import Service


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @api_method(InterfaceLagSupportedProtocolsArgs, InterfaceLagSupportedProtocolsResult, authorization_required=False)
    async def lag_supported_protocols(self):
        """
        Returns the link aggregation protocols that :method:`interface.create` and :method:`interface.update`
        accept for a bond.
        """
        return ['LACP', 'FAILOVER', 'LOADBALANCE']
