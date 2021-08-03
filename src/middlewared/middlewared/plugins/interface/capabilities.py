from middlewared.service_exception import ValidationErrors
from middlewared.service import Service, private
from middlewared.schema import Dict, Str, List, accepts, returns
from middlewared.plugins.interface.netif_linux import ethernet_settings


EHS = ethernet_settings.EthernetHardwareSettings


class InterfaceCapabilitiesService(Service):

    class Config:
        namespace = 'interface.capabilities'
        namespace_alias = 'interface.features'
        cli_namespace = 'network.interface.capabilities'

    @private
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

    @accepts(Str('name', required=True))
    @returns(Dict(
        'capabilties',
        List('enabled', items=[Str('capability')], required=True),
        List('disabled', items=[Str('capability')], required=True),
        List('supported', items=[Str('capability')], required=True),
    ))
    def get(self, name):
        """
        Return enabled, disabled and supported capabilities (also known as features)
        on a given interface.

        `name` String representing name of the interface
        """
        with EHS(name) as dev:
            return dev._caps

    @accepts(Dict(
        'capabilities_set',
        Str('name', required=True),
        List('capabilties', required=True),
        Str('action', enum=['ENABLE', 'DISABLE'], required=True),
    ))
    @returns(List('capabilities', items=[Str('capability')], required=True))
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
