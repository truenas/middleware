from middlewared.service import Service, private

from .netif import netif


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    def destroy(self, name):
        netif.destroy_interface(name)
