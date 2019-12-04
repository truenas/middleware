from middlewared.schema import accepts, Str
from middlewared.service import job, private, ServicePartBase


class DiskSyncBase(ServicePartBase):
    @private
    @accepts()
    @job(lock='disk.sync_all')
    async def sync_all(self, job):
        """
        Synchronize all disks with the cache in database.
        """

    @private
    @accepts(Str('name'))
    async def sync(self, name):
        """
        Syncs a disk `name` with the database cache.
        """
