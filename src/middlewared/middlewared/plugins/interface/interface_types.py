from enum import Enum

from middlewared.service import private, Service


class InterfaceType(Enum):
    BRIDGE = 'BRIDGE'
    LINK_AGGREGATION = 'LINK_AGGREGATION'
    PHYSICAL = 'PHYSICAL'
    UNKNOWN = 'UNKNOWN'
    VLAN = 'VLAN'


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    async def type(self, iface_state):
        if iface_state['name'].startswith(('br', 'kube-bridge')):
            return InterfaceType.BRIDGE
        elif iface_state['name'].startswith('bond'):
            return InterfaceType.LINK_AGGREGATION
        elif iface_state['name'].startswith('vlan'):
            return InterfaceType.VLAN
        elif not iface_state['cloned']:
            return InterfaceType.PHYSICAL
        else:
            return InterfaceType.UNKNOWN

    @private
    async def validate_name(self, type, name):
        if type == InterfaceType.BRIDGE:
            if not (name.startswith('br') and name[2:].isdigit()):
                raise ValueError('Bridge interface must start with "br" followed by an unique number.')

        if type == InterfaceType.LINK_AGGREGATION:
            if not (name.startswith('bond') and name[4:].isdigit()):
                raise ValueError('Link aggregation interface must start with "bond" followed by an unique number.')

        if type == InterfaceType.VLAN:
            if not (name.startswith('vlan') and name[4:].isdigit()):
                raise ValueError('VLAN interface must start with "vlan" followed by an unique number.')
