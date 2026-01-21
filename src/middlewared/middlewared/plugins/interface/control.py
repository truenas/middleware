from truenas_pynetif.netif import destroy_interface

from middlewared.service import Service, private


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    def destroy(self, name):
        destroy_interface(name)
