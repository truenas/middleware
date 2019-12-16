from middlewared.schema import accepts, Dict, Int, Str
from middlewared.service import private, ServicePartBase


class BootDiskBase(ServicePartBase):

    @private
    async def install_loader(self, dev):
        raise NotImplementedError()
