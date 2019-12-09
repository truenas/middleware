import re

from middlewared.service import private, ServicePartBase

RE_SERIAL_NUMBER = re.compile(r'Serial Number:\s+(?P<serial>.+)', re.I)


class DeviceInfoBase(ServicePartBase):

    RE_SERIAL_NUMBER = RE_SERIAL_NUMBER
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
    async def get_valid_zfs_partition_type_uuids(self):
        raise NotImplementedError()

    @private
    async def get_valid_swap_partition_type_uuids(self):
        raise NotImplementedError()
