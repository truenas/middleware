import enum

from middlewared.service import private, ServicePartBase


class InterfaceType(enum.Enum):
    BRIDGE = 'BRIDGE'
    LINK_AGGREGATION = 'LINK_AGGREGATION'
    PHYSICAL = 'PHYSICAL'
    UNKNOWN = 'UNKNOWN'
    VLAN = 'VLAN'


class InterfaceTypeBase(ServicePartBase):
    @private
    async def type(self, iface_state):
        raise NotImplementedError

    @private
    async def get_next_name(self, type):
        raise NotImplementedError

    @private
    async def validate_name(self, type, name):
        raise NotImplementedError
