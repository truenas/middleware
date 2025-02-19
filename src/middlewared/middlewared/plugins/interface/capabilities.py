from middlewared.service_exception import ValidationErrors
from middlewared.service import Service
from middlewared.plugins.interface.netif_linux import ethernet_settings


EHS = ethernet_settings.EthernetHardwareSettings


class InterfaceCapabilitiesService(Service):

    class Config:
        namespace = 'interface.capabilities'
        private = True
        namespace_alias = 'interface.features'
        cli_namespace = 'network.interface.capabilities'

    async def validate(self, data, dev):
        verrors = ValidationErrors()
        unavail = [i for i in data['capabilities'] if i not in dev.supported_capabilities]
        if unavail:
            # gave us a capability that isn't supported on the device
            # or is "fixed" (meaning it can't be changed)
            verrors.add(
                f'capabilities_set.{data["action"]}',
                f'"{data["name"]}" does not support "{", ".join(unavail)}"'
            )
        verrors.check()

    def get(self, name):
        """
        Return enabled, disabled and supported capabilities (also known as features)
        on a given interface.

        `name` String representing name of the interface
        """
        with EHS(name) as dev:
            return dev._caps

    def set(self, data):
        """
        Enable or Disable capabilties (also known as features) on a given interface.

        `name` String representing name of the interface
        `capabilities` List representing capabilities to be acted upon
        `action` String when set to 'ENABLE' will enable `capabilities` else if set
                    to `DISABLE` will disable `capabilities`.
        """
        with EHS(data['name']) as dev:
            self.middleware.call_sync('interface.capabilities.validate', data, dev)

            if data['action'] == 'enable':
                dev.enabled_capabilities = data['capabilities']
            else:
                dev.disabled_capabilities = data['capabilities']

        caps = self.middleware.call_sync('interface.capabilities.get', data['name'])
        return caps['enabled'] if data['action'] == 'ENABLE' else caps['disabled']
