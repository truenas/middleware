import re
from xml.etree import ElementTree as etree

import sysctl
from bsd.devinfo import DevInfo
from bsd.disk import get_ident_with_name
from .device_info_base import DeviceInfoBase
from middlewared.common.camcontrol import camcontrol_list
from middlewared.service import private, Service


RE_DISK_NAME = re.compile(r'^([a-z]+)([0-9]+)$')


class DeviceService(Service, DeviceInfoBase):

    async def get_disks(self):
        return await self.middleware.call('device.get_disk_details', 'DISK')

    async def get_disk(self, name):
        class_name = 'MULTIPATH' if name.startswith('multipath/') else 'DISK'
        disk = await self.middleware.call('device.get_disk_details', class_name, name)
        return None if not disk else disk

    @private
    def get_disk_details(self, class_name, disk_name=None):
        xml = etree.fromstring(sysctl.filter('kern.geom.confxml')[0].value).find(f'.//class/[name="{class_name}"]')
        devices = self.middleware.call_sync('device.get_storage_devices_topology')

        result = {}
        for g in xml.findall('geom'):
            name = g.find('provider/name').text
            if name.startswith('cd'):
                # ignore cd devices
                continue

            # means a singular disk was given to us so we need
            # to skip the disks until we hit the one that we want
            if disk_name is not None and disk_name != name:
                continue

            # make a copy of disk template
            disk = self.disk_default.copy()

            # sizes
            disk.update({
                'name': name,
                'mediasize': int(g.find('provider/mediasize').text),
                'sectorsize': int(g.find('provider/sectorsize').text),
                'stripesize': int(g.find('provider/stripesize').text),
            })

            config = g.find('provider/config')
            if config:
                # unique identifiers
                disk.update({i.tag: i.text for i in config if i.tag not in ('fwheads', 'fwsectors')})
                if disk['rotationrate'] is not None:
                    # rotation rate
                    disk['rotationrate'] = int(disk['rotationrate']) if disk['rotationrate'].isdigit() else None
                    if disk['rotationrate'] is not None:
                        if disk['rotationrate'] == 0:
                            disk['type'] = 'SSD'
                            disk['rotationrate'] = None
                        else:
                            disk['type'] = 'HDD'

                # description and model (they're the same)
                disk['descr'] = None if not disk['descr'] else disk['descr']
                disk['model'] = disk['descr']

                # if geom doesn't give us a serial then try again
                # (even though this is 100% guaranteed to return
                #   what geom sees)
                if not disk['ident']:
                    try:
                        disk['ident'] = get_ident_with_name(name)
                    except Exception:
                        disk['ident'] = ''

            # sprinkle our own information here
            reg = RE_DISK_NAME.search(name)
            if reg:
                disk['subsystem'] = reg.group(1)
                disk['number'] = int(reg.group(2))

            # API backwards compatibility dictates that we keep the
            # serial and size keys in the output
            disk['serial'] = disk['ident']
            disk['size'] = disk['mediasize']

            # some more sprinkling of our own information
            if disk['serial'] and disk['lunid']:
                disk['serial_lunid'] = f'{disk["serial"]}_{disk["lunid"]}'
            if disk['size'] and disk['sectorsize']:
                disk['blocks'] = int(disk['size'] / disk['sectorsize'])

            driver = devices.get(name, {}).get('driver')
            if driver == 'umass-sim':
                disk['bus'] = 'USB'
            else:
                disk['bus'] = 'UNKNOWN'

            if disk_name is not None:
                # this means that a singular disk was requested so
                # return here since we're iterating over all disks
                # on the system
                return disk
            else:
                # this means we're building the object for all the
                # disks on the system so update our result dict
                result[name] = disk
                continue

        return result

    async def get_serials(self):
        ports = []
        for devices in DevInfo().resource_managers['I/O ports'].values():
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
