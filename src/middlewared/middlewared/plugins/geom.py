import re
import threading
from xml.etree import ElementTree as etree

import sysctl
from middlewared.service import Service
from bsd.disk import get_ident_with_name


class GeomCache(Service):
    DISKS = {}  # formatted cache for geom DISKS (parsed xml)
    XML = None  # raw xml cache
    LOCK = threading.Lock()
    RE_DISK_NAME = re.compile(r'^([a-z]+)([0-9]+)$')
    CLASSES = ('PART', 'MULTIPATH', 'DISK', 'LABEL', 'DEV', 'RAID')
    DISK_TEMPLATE = {
        'name': None,
        'mediasize': None,
        'sectorsize': None,
        'stripesize': None,
        'rotationrate': None,
        'ident': '',
        'lunid': None,
        'descr': None,
        'subsystem': '',
        'number': 1,  # Database defaults
        'model': None,
        'type': 'UNKNOWN',
        'serial': '',
        'size': None,
        'serial_lunid': None,
        'blocks': None,
    }

    class Config:
        namespace = 'geom.cache'
        private = True

    def get_disks(self):
        return self.DISKS

    def get_xml(self):
        return self.XML

    def get_class_xml(self, class_name):
        if self.XML is not None:
            class_name = class_name.upper()
            if class_name in self.CLASSES:
                return self.XML.find(f'.//class[name="{class_name}"]')

    def invalidate_cache(self):
        self.middleware.call_sync('geom.cache.fill')

    def remove_disk(self, disk):
        with self.LOCK:
            self.DISKS.pop(disk, None).remove(disk)
            ele = self.XML.find(f'.//class[name="DISK"]/geom[name="{disk}"]')
            if ele:
                self.XML.find('.//class[name="DISK"]').remove(ele)

    def fill(self):
        with self.LOCK:
            self.XML = etree.fromstring(sysctl.filter('kern.geom.confxml')[0].value)
            for i in self.XML.iterfind('.//class[name="DISK"]/geom'):
                name = i.find('provider/name').text
                if name.startswith('cd'):
                    # ignore cd devices
                    continue

                # make a copy of disk template
                disk = self.DISK_TEMPLATE.copy()

                # sizes
                disk.update({
                    'name': name,
                    'mediasize': int(i.find('provider/mediasize').text),
                    'sectorsize': int(i.find('provider/sectorsize').text),
                    'stripesize': int(i.find('provider/stripesize').text),
                })

                config = i.find('provider/config')
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
                    #   what geom gave us)
                    if not disk['ident']:
                        try:
                            disk['ident'] = get_ident_with_name(name)
                        except Exception:
                            disk['ident'] = ''

                # sprinkle our own information here
                reg = self.RE_DISK_NAME.search(name)
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

                # update the cache with the disk info
                self.DISKS[name] = disk


async def setup(middleware):
    await middleware.call('geom.cache.fill')
