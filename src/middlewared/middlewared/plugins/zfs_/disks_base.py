from middlewared.schema import accepts, Str
from middlewared.service import ServicePartBase


class PoolDiskServiceBase(ServicePartBase):

    @accepts(Str('pool'))
    def get_disks(self, name):
        raise NotImplementedError()
