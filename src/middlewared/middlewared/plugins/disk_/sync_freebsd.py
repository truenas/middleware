import os

from bsd import geom
from datetime import datetime, timedelta
from lxml import etree
from xml.etree import ElementTree

from middlewared.service import private, Service, ServiceChangeMixin

from .sync_base import DiskSyncBase


RAWTYPE = {
    'freebsd-zfs': '516e7cba-6ecf-11d6-8ff8-00022d09712b',
    'freebsd-swap': '516e7cb5-6ecf-11d6-8ff8-00022d09712b',
}


class DiskService(Service, DiskSyncBase, ServiceChangeMixin):

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
            disk['disk_serial'] = await self.serial_from_device(name) or ''
        reg = self.RE_DISK_NAME.search(name)
        if reg:
            disk['disk_subsystem'] = reg.group(1)
            disk['disk_number'] = int(reg.group(2))
        return g

    async def sync(self, name):
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

        await self.restart_services_after_sync()

        if not await self.middleware.call('system.is_freenas'):
            await self.middleware.call('enclosure.sync_disk', disk['disk_identifier'])

    async def sync_all(self, job):
        # Skip sync disks on standby node
        if (
            not await self.middleware.call('system.is_freenas') and
            await self.middleware.call('failover.licensed') and
            await self.middleware.call('failover.status') == 'BACKUP'
        ):
            return

        sys_disks = list((await self.middleware.call('device.get_info', 'DISK')).keys())

        seen_disks = {}
        serials = []
        changed = False
        await self.middleware.run_in_thread(geom.scan)
        for disk in (
            await self.middleware.call('datastore.query', 'storage.disk', [], {'order_by': ['disk_expiretime']})
        ):

            original_disk = disk.copy()

            name = await self.middleware.call('disk.identifier_to_device', disk['disk_identifier'])
            if not name or name in seen_disks:
                # If we cant translate the identifier to a device, give up
                # If name has already been seen once then we are probably
                # dealing with with multipath here
                if not disk['disk_expiretime']:
                    disk['disk_expiretime'] = datetime.utcnow() + timedelta(days=self.DISK_EXPIRECACHE_DAYS)
                    await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
                    changed = True
                elif disk['disk_expiretime'] < datetime.utcnow():
                    # Disk expire time has surpassed, go ahead and remove it
                    for extent in await self.middleware.call(
                        'iscsi.extent.query', [['type', '=', 'DISK'], ['path', '=', disk['disk_identifier']]]
                    ):
                        await self.middleware.call('iscsi.extent.delete', extent['id'])
                    await self.middleware.call('datastore.delete', 'storage.disk', disk['disk_identifier'])
                    changed = True
                continue
            else:
                disk['disk_expiretime'] = None
                disk['disk_name'] = name

            g = await self.__disk_data(disk, name)
            serial = disk.get('disk_serial') or ''
            if g:
                serial += g.provider.config.get('lunid') or ''

            if serial:
                serials.append(serial)

            # If for some reason disk is not identified as a system disk
            # mark it to expire.
            if name not in sys_disks and not disk['disk_expiretime']:
                disk['disk_expiretime'] = datetime.utcnow() + timedelta(days=self.DISK_EXPIRECACHE_DAYS)
            # Do not issue unnecessary updates, they are slow on HA systems and cause severe boot delays
            # when lots of drives are present
            if disk != original_disk:
                await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
                changed = True

            if not await self.middleware.call('system.is_freenas'):
                await self.middleware.call('enclosure.sync_disk', disk['disk_identifier'])

            seen_disks[name] = disk

        for name in sys_disks:
            if name not in seen_disks:
                disk_identifier = await self.middleware.call('disk.device_to_identifier', name)
                qs = await self.middleware.call(
                    'datastore.query', 'storage.disk', [('disk_identifier', '=', disk_identifier)]
                )
                if qs:
                    new = False
                    disk = qs[0]
                else:
                    new = True
                    disk = {'disk_identifier': disk_identifier}
                original_disk = disk.copy()
                disk['disk_name'] = name
                serial = ''
                g = geom.geom_by_name('DISK', name)
                if g:
                    if g.provider.config['ident']:
                        serial = disk['disk_serial'] = g.provider.config['ident']
                    serial += g.provider.config.get('lunid') or ''
                    if g.provider.mediasize:
                        disk['disk_size'] = g.provider.mediasize
                if not disk.get('disk_serial'):
                    serial = disk['disk_serial'] = await self.serial_from_device(name) or ''
                if serial:
                    if serial in serials:
                        # Probably dealing with multipath here, do not add another
                        continue
                    else:
                        serials.append(serial)
                reg = self.RE_DISK_NAME.search(name)
                if reg:
                    disk['disk_subsystem'] = reg.group(1)
                    disk['disk_number'] = int(reg.group(2))

                if not new:
                    # Do not issue unnecessary updates, they are slow on HA systems and cause severe boot delays
                    # when lots of drives are present
                    if disk != original_disk:
                        await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
                        changed = True
                else:
                    disk['disk_identifier'] = await self.middleware.call('datastore.insert', 'storage.disk', disk)
                    changed = True

                if not await self.middleware.call('system.is_freenas'):
                    await self.middleware.call('enclosure.sync_disk', disk['disk_identifier'])

        if changed:
            await self.restart_services_after_sync()
        return 'OK'

    @private
    async def restart_services_after_sync(self):
        await self.middleware.call('disk.update_hddstandby_force')
        await self.middleware.call('disk.update_smartctl_args_for_disks')
        if await self.middleware.call('service.started', 'collectd'):
            await self.middleware.call('service.restart', 'collectd')
        await self._service_change('smartd', 'restart')
        await self._service_change('snmp', 'restart')

    async def device_to_identifier(self, name):
        await self.middleware.run_in_thread(geom.scan)

        g = geom.geom_by_name('DISK', name)
        if g and g.provider.config.get('ident'):
            serial = g.provider.config['ident']
            lunid = g.provider.config.get('lunid')
            if lunid:
                return f'{{serial_lunid}}{serial}_{lunid}'
            return f'{{serial}}{serial}'

        serial = await self.serial_from_device(name)
        if serial:
            return f'{{serial}}{serial}'

        klass = geom.class_by_name('PART')
        if klass:
            for g in klass.geoms:
                for p in g.providers:
                    if p.name == name:
                        if p.config['rawtype'] == RAWTYPE['freebsd-zfs']:
                            return f'{{uuid}}{p.config["rawuuid"]}'

        g = geom.geom_by_name('LABEL', name)
        if g:
            return f'{{label}}{g.provider.name}'

        g = geom.geom_by_name('DEV', name)
        if g:
            return f'{{devicename}}{name}'

        return ''

    def identifier_to_device(self, ident):

        if not ident:
            return None

        search = self.RE_IDENTIFIER.search(ident)
        if not search:
            return None

        geom.scan()

        tp = search.group('type')
        # We need to escape single quotes to html entity
        value = search.group('value').replace("'", '%27')

        if tp == 'uuid':
            search = geom.class_by_name('PART').xml.find(
                f'.//config[rawuuid = "{value}"]/../../name'
            )
            if search is not None and not search.text.startswith('label'):
                return search.text

        elif tp == 'label':
            search = geom.class_by_name('LABEL').xml.find(
                f'.//provider[name = "{value}"]/../name'
            )
            if search is not None:
                return search.text

        elif tp == 'serial':
            search = geom.class_by_name('DISK').xml.find(
                f'.//provider/config[ident = "{value}"]/../../name'
            )
            if search is not None:
                return search.text
            # Builtin xml xpath do not understand normalize-space
            search = etree.fromstring(ElementTree.tostring(geom.class_by_name('DISK').xml))
            search = search.xpath(
                './/provider/config['
                f'normalize-space(ident) = normalize-space("{value}")'
                ']/../../name'
            )
            if len(search) > 0:
                return search[0].text
            disks = self.middleware.call_sync('disk.query', [('serial', '=', value)])
            if disks:
                return disks[0]['name']

        elif tp == 'serial_lunid':
            # Builtin xml xpath do not understand concat
            search = etree.fromstring(ElementTree.tostring(geom.class_by_name('DISK').xml))
            search = search.xpath(
                f'.//provider/config[concat(ident,"_",lunid) = "{value}"]/../../name'
            )
            if len(search) > 0:
                return search[0].text

        elif tp == 'devicename':
            if os.path.exists(f'/dev/{value}'):
                return value
        else:
            raise NotImplementedError(f'Unknown type {tp!r}')

    async def serial_from_device(self, name):
        output = await self.middleware.call('disk.smartctl', name, ['-i'], {'cache': False, 'silent': True})
        if output:
            search = self.RE_SERIAL_NUMBER.search(output)
            if search:
                return search.group('serial')

        await self.middleware.run_in_thread(geom.scan)
        g = geom.geom_by_name('DISK', name)
        if g and g.provider.config.get('ident'):
            return g.provider.config['ident']

        return None
