import netif

from middlewared.service import Service

from .capabilities_base import InterfaceCapabilitiesBase


class InterfaceService(Service, InterfaceCapabilitiesBase):

    class Config:
        namespace_alias = 'interfaces'

    async def nic_capabilities(self):
        return [c for c in netif.InterfaceCapability.__members__]

    async def to_disable_evil_nic_capabilities(self, check_iface=True):
        return list(await self.middleware.call('vm.device.nic_capability_checks', None, check_iface))

    def enable_capabilities(self, iface, capabilities):
        enabled = []
        iface = netif.get_interface(iface)
        for capability in map(lambda c: getattr(netif.InterfaceCapability, c), capabilities):
            current = iface.capabilities
            if capability in current:
                continue
            try:
                iface.capabilities = current | {capability}
            except OSError:
                pass
            else:
                enabled.append(capability.name)
        if enabled:
            self.middleware.logger.debug(f'Enabled {",".join(enabled)} capabilities for {iface}')

    def disable_capabilities(self, iface, capabilities):
        self.middleware.call_sync('interface.get_instance', iface)
        iface = netif.get_interface(iface)
        disabled_capabilities = [c.name for c in iface.capabilities if c.name in capabilities]
        iface.capabilities = {c for c in iface.capabilities if c.name not in capabilities}
        if disabled_capabilities:
            self.middleware.logger.debug(f'Disabling {",".join(disabled_capabilities)} capabilities for {iface}')
