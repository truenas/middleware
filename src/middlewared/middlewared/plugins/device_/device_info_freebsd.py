import re

from bsd import geom, devinfo

from .device_info_base import DeviceInfoBase

from middlewared.common.camcontrol import camcontrol_list
from middlewared.service import private, Service


RE_DISK_NAME = re.compile(r'^([a-z]+)([0-9]+)$')


class DeviceService(Service, DeviceInfoBase):

    async def get_disks(self):
        disks = {}
        klass = await self.middleware.call('device.retrieve_geom_class', 'DISK')
        if not klass:
            return disks
        for g in klass.geoms:
            # Skip cd*
            if g.name.startswith('cd'):
                continue
            disks[g.name] = await self.get_disk_details(self.disk_default.copy(), g)
        return disks

    @private
    def retrieve_geom_class(self, class_name):
        geom.scan()
        return geom.class_by_name(class_name)

    async def get_disk(self, name):
        disk = self.disk_default.copy()
        if name.startswith('multipath/'):
            disk_klass = await self.middleware.call('device.retrieve_geom_class', 'MULTIPATH')
        else:
            disk_klass = await self.middleware.call('device.retrieve_geom_class', 'DISK')
        if not disk_klass:
            return None
        disk_geom = next((g for g in disk_klass.geoms if g.name == (
            name if disk_klass.name == 'DISK' else name.split('/')[-1]
        )), None)
        if not disk_geom:
            return None
        return await self.get_disk_details({**disk, 'name': name}, disk_geom)

    @private
    async def get_disk_details(self, disk, disk_geom):
        disk.update({
            'name': disk_geom.name if not disk['name'] else disk['name'],
            'mediasize': disk_geom.provider.mediasize,
            'sectorsize': disk_geom.provider.sectorsize,
            'stripesize': disk_geom.provider.stripesize,
        })
        if disk_geom.provider.config:
            disk.update({k: v for k, v in disk_geom.provider.config.items() if k not in ('fwheads', 'fwsectors')})
            if disk['rotationrate'] is not None:
                disk['rotationrate'] = int(disk['rotationrate']) if disk['rotationrate'].isdigit() else None
            if not disk['descr']:
                disk['descr'] = None
            disk['model'] = disk['descr']

            if disk['rotationrate'] is not None:
                if disk['rotationrate'] == 0:
                    disk['rotationrate'] = None
                    disk['type'] = 'SSD'
                else:
                    disk['type'] = 'HDD'
            elif disk_geom.provider.config.get('rotationrate') != 'unknown':
                self.middleware.logger.debug(
                    'Unable to retrieve rotation rate for %s. Rotation rate reported by DISK geom is "%s"',
                    disk['name'], disk_geom.provider.config.get('rotationrate')
                )

        if not disk['ident']:
            output = await self.middleware.call(
                'disk.smartctl', disk_geom.name, ['-i'], {'cache': False, 'silent': True}
            )
            if output:
                search = self.RE_SERIAL_NUMBER.search(output)
                if search:
                    disk['ident'] = search.group('serial')

        if not disk['ident']:
            disk['ident'] = ''

        reg = RE_DISK_NAME.search(disk_geom.name)
        if reg:
            disk['subsystem'] = reg.group(1)
            disk['number'] = int(reg.group(2))

        # We still keep ident/mediasize to not break previous api users
        disk['serial'] = disk['ident']
        disk['size'] = disk['mediasize']
        if disk['serial'] and disk['lunid']:
            disk['serial_lunid'] = f'{disk["serial"]}_{disk["lunid"]}'
        if disk['size'] and disk['sectorsize']:
            disk['blocks'] = int(disk['size'] / disk['sectorsize'])

        return disk

    async def get_serials(self):
        ports = []
        for devices in devinfo.DevInfo().resource_managers['I/O ports'].values():
            for dev in devices:
                if not dev.name.startswith('uart'):
                    continue
                port = self.serial_port_default.copy()
                port.update({
                    'name': dev.name,
                    'description': dev.desc,
                    'drivername': dev.drivername,
                    'location': dev.location,
                    'start': hex(dev.start),
                    'size': dev.size
                })
                ports.append(port)
        return ports

    async def get_storage_devices_topology(self):
        return await camcontrol_list()

    async def get_gpus(self):
        raise NotImplementedError()
