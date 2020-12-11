import re

from middlewared.service import private, ServicePartBase


class DeviceInfoBase(ServicePartBase):

    RE_SERIAL_NUMBER = re.compile(r'Serial Number:\s+(?P<serial>.+)', re.I)
    serial_port_default = {
        'name': None,
        'location': None,
        'drivername': 'uart',
        'description': None,
        'start': None,
        'size': None,
    }
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
        'blocks': None,
    }

    @private
    async def get_gpus(self):
        raise NotImplementedError()

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
    async def get_storage_devices_topology(self):
        raise NotImplementedError()
