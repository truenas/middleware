import re

from middlewared.schema import accepts, Str
from middlewared.service import job, private, ServiceChangeMixin, ServicePartBase

RE_DISKNAME = re.compile(r'^([a-z]+)([0-9]+)$')


class DiskSyncBase(ServicePartBase, ServiceChangeMixin):

    DISK_EXPIRECACHE_DAYS = 7
    RE_DISK_NAME = RE_DISKNAME

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
