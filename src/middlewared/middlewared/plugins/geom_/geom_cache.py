from time import sleep
from threading import Lock, Thread, Event
from re import compile as rcompile
from xml.etree import ElementTree as etree

from sysctl import filter as sfilter
from bsd.disk import get_ident_with_name


class GeomCacheThread(Thread):

    RE_DISK_NAME = rcompile(r'^([a-z]+)([0-9]+)$')
    DISKS = {}  # formatted cache for geom DISKS (parsed XML)
    XML = None  # raw xml cache
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

    def __init__(self, *args, **kwargs):
        super(GeomCacheThread, self).__init__(*args, **kwargs)
        self._invalidate = Event()
        self._stop = Event()
        self._lock = Lock()

    @property
    def disks(self):
        return self.DISKS

    @property
    def xml(self):
        return self.XML

    def invalidate(self):
        self._invalidate.set()
        while self._invalidate.is_set():
            sleep(0.1)

    def stop(self):
        self._stop.set()

    def add(self, disk=None):
        # received a request to add a disk to the cache
        # adding a disk means we have to ask the kernel for the geom xml
        # information (in its entirety) and create an xml object. Creating
        # the xml object is the expensive part. We do not gain any cpu time
        # or "speed up" by doing anything clever in this scenario.
        self.invalidate()

    def remove(self, disk):
        # received a request to remove a disk from the cache
        # which means we don't need to invalidate the entirety
        # of the cache just need to remove the disk from
        # `self.XML` and `self.DISKS`
        with self._lock:
            self.DISKS.pop(disk, None)
            if self.XML is not None:
                ele = self.XML.find(f'.//class[name="DISK"]/geom[name="{disk}"]')
                if ele:
                    self.XML.find('.//class[name="DISK"]').remove(ele)

    def run(self):
        while True:
            if self._invalidate.is_set():
                # either we were requested to invalidate the entire cache
                # or a devd event was triggered that a disk is added to
                # the system. If a disk is added, we have to request all
                # of the xml and then parse it (the expensive part) so
                # this is why we treat an addition of a drive the same as
                # invalidating the cache.
                self.fill(invalidate=True)
                self._invalidate.clear()
            elif self._stop.is_set():
                # middlewared or system is going down/rebooting etc
                return
            elif not self.DISKS or self.XML is None:
                # thread is initially starting so need to fill up the cache
                self.fill()
            else:
                sleep(0.1)

    def fill(self, invalidate=False):
        with self._lock:
            if invalidate or self.XML is None or not self.DISKS:
                self.XML = etree.fromstring(sfilter('kern.geom.confxml')[0].value)
                for i in self.XML.findall('.//class[name="DISK"]geom'):
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
