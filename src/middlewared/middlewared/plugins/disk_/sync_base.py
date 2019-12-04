import re

from middlewared.schema import accepts, Str
from middlewared.service import job, private, ServicePartBase

RE_DISKNAME = re.compile(r'^([a-z]+)([0-9]+)$')


class DiskSyncBase(ServicePartBase):

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

    @private
    @accepts(Str('name'))
    async def device_to_identifier(self, name):
        """
        Given a device `name` (e.g. da0) returns an unique identifier string
        for this device.
        This identifier is in the form of {type}string, "type" can be one of
        the following:
          - serial_lunid - for disk serial concatenated with the lunid
          - serial - disk serial
          - uuid - uuid of a ZFS GPT partition
          - label - label name from geom label
          - devicename - name of the device if any other could not be used/found

        Returns:
            str - identifier
        """

    @private
    async def serial_from_device(self, name):
        raise NotImplementedError()
