import truenas_pynetif as netif

from middlewared.service import private, Service


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    async def internal_interfaces(self):
        # expicit call to list() is important here
        result = list(netif.INTERNAL_INTERFACES)
        result.extend(await self.middleware.call('failover.internal_interface.detect'))
        result.extend(await self.middleware.call('rdma.interface.internal_interfaces'))
        result.extend(await self.middleware.call('virt.global.internal_interfaces'))
        if (await self.middleware.call('truenas.get_chassis_hardware')).startswith('TRUENAS-F'):
            # The eno1 interface needs to be masked on the f-series platform because
            # this interface is shared with the BMC. Details for why this is done
            # can be obtained from platform team.
            result.append('eno1')

        return result + await self.middleware.call('docker.network.interfaces_mapping')
