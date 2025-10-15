from typing import get_args, Literal, TypedDict

from truenas_pynetif.ethernet_settings import EthernetHardwareSettings

from middlewared.service_exception import ValidationError
from middlewared.service import Service


class GetCapabilities(TypedDict):
    enabled: list[str]
    """Interface capabilities that are enabled."""
    disabled: list[str]
    """Interface capabilities that are disabled."""
    supported: list[str]
    """Interface capabilities that are supported."""


class SetCapabilties(TypedDict):
    name: str
    """Name of the ethernet device"""
    capabilities: list[str]
    """List of capabilities (features) to perform `action` upon"""
    action: Literal['ENABLE', 'DISABLE']
    """ENABLE or DISABLE `capabilities` on ethernet device"""


class InterfaceCapabilitiesService(Service):

    class Config:
        private = True
        namespace = 'interface.capabilities'
        namespace_alias = 'interface.features'

    async def validate(self, data, dev):
        action = data.get('action')
        if not action or action not in get_args(SetCapabilties.__annotations__['action']):
            raise ValidationError(
                f'{self._config.namespace}.action',
                '"action" needs to be "ENABLE" or "DISABLE'
            )

        caps = data.get('capabilities')
        if not caps:
            raise ValidationError(
                f'{self._config.namespace}.capabilities',
                '"capabilities" is required'
            )

        supported_caps = dev.supported_capabilities
        for cap in caps:
            if not isinstance(cap, str):
                raise ValidationError(
                    f'{self._config.namespace}.capabilities',
                    '"capabilities" should be a list of strings'
                )
            elif cap not in supported_caps:
                raise ValidationError(
                    f'{self._config.namespace}.capabilities',
                    f'{cap} is not supported on {data["name"]}'
                )

    def get(self, name: str) -> GetCapabilities:
        """
        Return enabled, disabled and supported capabilities (also known as features)
        on a given interface.

        `name` String representing name of the interface
        """
        with EthernetHardwareSettings(name) as dev:
            return dev._caps

    def set(self, data: SetCapabilties) -> list[str]:
        """
        Enable or Disable capabilties (also known as features) on a given interface.

        `name` String representing name of the interface
        `capabilities` List representing capabilities to be acted upon
        `action` String when set to `ENABLE` will enable `capabilities` else if set
                    to `DISABLE` will disable `capabilities`.
        """
        if not data.get('name'):
            raise ValidationError(
                f'{self._config.namespace}.name',
                '"name" is required'
            )

        with EthernetHardwareSettings(data['name']) as dev:
            self.validate(data, dev)
            if data['action'] == 'ENABLE':
                dev.enabled_capabilities = data['capabilities']
            else:
                dev.disabled_capabilities = data['capabilities']
        caps = self.get(data['name'])
        return caps['enabled'] if data['action'] == 'ENABLE' else caps['disabled']
