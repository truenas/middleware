from middlewared.service import private, ServicePartBase


class InterfaceInfoBase(ServicePartBase):

    @private
    async def internal_interfaces(self):
        raise NotImplementedError
