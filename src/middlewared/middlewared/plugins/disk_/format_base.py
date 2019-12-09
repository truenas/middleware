from middlewared.service import private, ServicePartBase


class FormatDiskBase(ServicePartBase):

    @private
    async def format(self, disk, swapgb, sync=True):
        raise NotImplementedError()
