from middlewared.service import private, ServicePartBase


class DeviceInfoBase(ServicePartBase):

    @private
    async def get_serial(self):
        raise NotImplementedError()

    @private
    async def get_disk(self):
        raise NotImplementedError()
