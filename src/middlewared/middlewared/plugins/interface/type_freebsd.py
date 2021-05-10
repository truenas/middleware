from middlewared.service import Service

from .type_base import InterfaceType, InterfaceTypeBase


class InterfaceService(Service, InterfaceTypeBase):

    class Config:
        namespace_alias = 'interfaces'

    async def type(self, iface_state):
        if iface_state['name'].startswith('bridge'):
            return InterfaceType.BRIDGE
        elif iface_state['name'].startswith('lagg'):
            return InterfaceType.LINK_AGGREGATION
        elif iface_state['name'].startswith('vlan'):
            return InterfaceType.VLAN
        elif not iface_state['cloned']:
            return InterfaceType.PHYSICAL
        else:
            return InterfaceType.UNKNOWN

    async def get_next_name(self, type):
        # For bridge we want to start with 2 because bridge0/bridge1 may have been used
        # for VM.
        if type == InterfaceType.BRIDGE:
            return await self.middleware.call('interface.get_next', 'bridge', 2)

        if type == InterfaceType.LINK_AGGREGATION:
            return await self.middleware.call('interface.get_next', 'lagg')

        raise ValueError(type)

    async def validate_name(self, type, name):
        if type == InterfaceType.BRIDGE:
            if not (name.startswith('bridge') and name[6:].isdigit()):
                raise ValueError('Bridge interface must start with "bridge" followed by an unique number.')

        if type == InterfaceType.LINK_AGGREGATION:
            if not (name.startswith('lagg') and name[4:].isdigit()):
                raise ValueError('Link aggregation interface must start with "lagg" followed by an unique number.')
            else:
                # lagg0 is allowed, lagg0X is not
                if len(name) > 5 and name[4] == '0':
                    raise ValueError('Link aggregation interface name cannot start with "lagg0".')

        if type == InterfaceType.VLAN:
            if not (name.startswith('vlan') and name[4:].isdigit()):
                raise ValueError('VLAN interface must start with "vlan" followed by an unique number.')
