from middlewared.service import private, Service

from .netif import netif


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    async def internal_interfaces(self):
        return netif.INTERNAL_INTERFACES
