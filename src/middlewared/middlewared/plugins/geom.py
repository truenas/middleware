import re
import threading
from xml.etree import ElementTree as etree
from itertools import zip_longest

import sysctl
from middlewared.service import Service
from bsd.disk import get_ident_with_name


class GeomCache(Service):
    DISKS = {}  # formatted cache for geom DISKS (parsed xml)
    MULTIPATH = {}  # formatted cache for geom MULTIPATH providers (parsed xml)
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

    def get_multipath(self):
        return self.MULTIPATH

    def get_xml(self):
        return self.XML

    def get_class_xml(self, class_name):
        if self.XML is not None:
            class_name = class_name.upper()
            if class_name in self.CLASSES:
                return self.XML.find(f'.//class[name="{class_name}"]')

    def invalidate(self):
        self.middleware.call_sync('geom.cache.fill')

    def remove_disk(self, disk):
        with self.LOCK:
            self.DISKS.pop(disk, None).remove(disk)
            ele = self.XML.find(f'.//class[name="DISK"]/geom[name="{disk}"]')
            if ele:
                self.XML.find('.//class[name="DISK"]').remove(ele)

    def _fill_disk_details(self, xmlelem):
        name = xmlelem.find('provider/name').text
        if name.startswith('cd'):
            # ignore cd devices
            return

        # make a copy of disk template
        disk = self.DISK_TEMPLATE.copy()

        # sizes
        disk.update({
            'name': name,
            'mediasize': int(xmlelem.find('provider/mediasize').text),
            'sectorsize': int(xmlelem.find('provider/sectorsize').text),
            'stripesize': int(xmlelem.find('provider/stripesize').text),
        })

        if config := xmlelem.find('provider/config'):
            # unique identifiers
            disk.update({i.tag: i.text for i in config if i.tag not in ('fwheads', 'fwsectors')})
            if disk['rotationrate'] is not None and disk['rotationrate'].isdigit():
                disk['rotationrate'] = int(disk['rotationrate'])
                if disk['rotationrate'] == 0:
                    disk['type'] = 'SSD'
                    disk['rotationrate'] = None
                else:
                    disk['type'] = 'HDD'

            # description and model (they're the same)
            disk['descr'] = disk['model'] = None if not disk['descr'] else disk['descr']

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

    def _fill_multipath_consumer_details(self, xmlelem):
        children = []
        for i in xmlelem.findall('./consumer'):
            consumer_status = i.find('./config/State').text
            provref = i.find('./provider').attrib['ref']
            prov = self.XML.findall(f'.//provider[@id="{provref}"]')[0]
            da_name = prov.find('./name').text
            try:
                lun_id = prov.find('./config/lunid').text
            except Exception:
                lun_id = ''

            children.append({
                'type': 'consumer',
                'name': da_name,
                'status': consumer_status,
                'lun_id': lun_id,
            })

        multipath_name = 'multipath/' + xmlelem.find('./name').text
        self.MULTIPATH[multipath_name] = {
            'type': 'root',
            'name': multipath_name,
            'status': xmlelem.find('./config/State').text,
            'children': children,
        }

    def fill(self):
        with self.LOCK:
            # wipe/overwrite the current cache
            self.XML = etree.fromstring(sysctl.filter('kern.geom.confxml')[0].value)
            self.MULTIPATH = {}
            self.DISKS = {}

            # grab the relevant xml classes and refill the cache objects
            _disks = self.XML.findall('.//class[name="DISK"]/geom')
            _mpdisks = self.XML.findall('.//class[name="MULTIPATH"]/geom')
            for disk, mpdisk in zip_longest(_disks, _mpdisks, fillvalue=None):
                if disk is not None:
                    self._fill_disk_details(disk)
                if mpdisk is not None:
                    self._fill_disk_details(mpdisk)
                    self._fill_multipath_consumer_details(mpdisk)


async def setup(middleware):
    await middleware.call('geom.cache.fill')
