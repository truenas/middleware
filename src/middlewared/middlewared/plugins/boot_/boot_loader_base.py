from middlewared.service import private, ServicePartBase


class BootLoaderBase(ServicePartBase):

    @private
    async def install_loader(self, dev):
        raise NotImplementedError()
