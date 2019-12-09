import re

from middlewared.service import private, ServicePartBase


class DeviceInfoBase(ServicePartBase):

    RE_SERIAL_NUMBER = re.compile(r'Serial Number:\s+(?P<serial>.+)', re.I)
    disk_default = {
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
    }

    @private
    async def get_serials(self):
        raise NotImplementedError()

    @private
    async def get_disks(self):
        raise NotImplementedError()

    @private
    async def get_disk(self, name):
        raise NotImplementedError()

    @private
    async def get_dev_size(self, dev):
        """
        Return disk/partition size in bytes or None if unable to do so
        """
