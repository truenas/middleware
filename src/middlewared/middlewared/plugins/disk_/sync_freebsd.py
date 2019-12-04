from bsd import geom
from datetime import datetime, timedelta

from middlewared.service import Service

from .sync_base import DiskSyncBase


class DiskService(Service, DiskSyncBase):

    async def __disk_data(self, disk, name):
        g = geom.geom_by_name('DISK', name)
        if g:
            if g.provider.config['ident']:
                disk['disk_serial'] = g.provider.config['ident']
            if g.provider.mediasize:
                disk['disk_size'] = g.provider.mediasize
            try:
                if g.provider.config['rotationrate'] == '0':
                    disk['disk_rotationrate'] = None
                    disk['disk_type'] = 'SSD'
                else:
                    disk['disk_rotationrate'] = int(g.provider.config['rotationrate'])
                    disk['disk_type'] = 'HDD'
            except ValueError:
                disk['disk_type'] = 'UNKNOWN'
                disk['disk_rotationrate'] = None
            disk['disk_model'] = g.provider.config['descr'] or None

        if not disk.get('disk_serial'):
            disk['disk_serial'] = await self.middleware.call('disk.serial_from_device', name) or ''
        reg = self.RE_DISK_NAME.search(name)
        if reg:
            disk['disk_subsystem'] = reg.group(1)
            disk['disk_number'] = int(reg.group(2))
        return g

    def sync(self, name):
        if (
            not await self.middleware.call('system.is_freenas') and
            await self.middleware.call('failover.licensed') and
            await self.middleware.call('failover.status') == 'BACKUP'
        ):
            return

        # Do not sync geom classes like multipath/hast/etc
        if name.find('/') != -1:
            return

        disks = list((await self.middleware.call('device.get_info', 'DISK')).keys())

        # Abort if the disk is not recognized as an available disk
        if name not in disks:
            return
        ident = await self.middleware.call('disk.device_to_identifier', name)
        qs = await self.middleware.call('datastore.query', 'storage.disk', [('disk_identifier', '=', ident)],
                                        {'order_by': ['disk_expiretime']})
        if ident and qs:
            disk = qs[0]
            new = False
        else:
            new = True
            qs = await self.middleware.call('datastore.query', 'storage.disk', [('disk_name', '=', name)])
            for i in qs:
                i['disk_expiretime'] = datetime.utcnow() + timedelta(days=self.DISK_EXPIRECACHE_DAYS)
                await self.middleware.call('datastore.update', 'storage.disk', i['disk_identifier'], i)
            disk = {'disk_identifier': ident}
        disk.update({'disk_name': name, 'disk_expiretime': None})

        await self.middleware.run_in_thread(geom.scan)
        await self.__disk_data(disk, name)

        if not new:
            await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
        else:
            disk['disk_identifier'] = await self.middleware.call('datastore.insert', 'storage.disk', disk)

        await self.middleware.call('disk.update_hddstandby_force')
        await self.middleware.call('disk.update_smartctl_args_for_disks')
        if await self.middleware.call('service.started', 'collectd'):
            await self.middleware.call('service.restart', 'collectd')
        await self._service_change('smartd', 'restart')
        await self._service_change('snmp', 'restart')

        if not await self.middleware.call('system.is_freenas'):
            await self.middleware.call('enclosure.sync_disk', disk['disk_identifier'])
