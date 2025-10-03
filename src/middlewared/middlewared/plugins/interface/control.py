import truenas_pynetif as netif

from middlewared.service import Service, private


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    def destroy(self, name):
        netif.destroy_interface(name)
