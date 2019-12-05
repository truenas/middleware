import re

from middlewared.schema import accepts, Str
from middlewared.service import job, private, ServicePartBase, ServiceChangeMixin

RE_DISKNAME = re.compile(r'^([a-z]+)([0-9]+)$')
RE_SMART_SERIAL_NUMBER = re.compile(r'Serial Number:\s+(?P<serial>.+)', re.I)
RE_IDENTIFIER = re.compile(r'^\{(?P<type>.+?)\}(?P<value>.+)$')


class DiskSyncBase(ServicePartBase):

    DISK_EXPIRECACHE_DAYS = 7
    RE_DISK_NAME = RE_DISKNAME
    RE_SERIAL_NUMBER = RE_SMART_SERIAL_NUMBER
    RE_IDENTIFIER = RE_IDENTIFIER

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


class DiskSyncMixin(ServiceChangeMixin):

    @private
    async def restart_services_after_sync(self):
        await self.middleware.call('disk.update_hddstandby_force')
        await self.middleware.call('disk.update_smartctl_args_for_disks')
        if await self.middleware.call('service.started', 'collectd'):
            await self.middleware.call('service.restart', 'collectd')
        await self._service_change('smartd', 'restart')
        await self._service_change('snmp', 'restart')
