import re

from middlewared.schema import accepts, Str
from middlewared.service import job, private, ServicePartBase

RE_DISKNAME = re.compile(r'^([a-z]+)([0-9]+)$')
RE_SMART_SERIAL_NUMBER = re.compile(r'Serial Number:\s+(?P<serial>.+)', re.I)


class DiskSyncBase(ServicePartBase):

    DISK_EXPIRECACHE_DAYS = 7
    RE_DISK_NAME = RE_DISKNAME
    RE_SERIAL_NUMBER = RE_SMART_SERIAL_NUMBER

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
    @accepts(Str('identifier'))
    def identifier_to_device(self, ident):
        raise NotImplementedError()
