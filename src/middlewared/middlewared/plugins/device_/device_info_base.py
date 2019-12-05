import re

from middlewared.service import private, ServicePartBase

RE_SERIAL_NUMBER = re.compile(r'Serial Number:\s+(?P<serial>.+)', re.I)
RE_DISK_NAME = re.compile(r'^([a-z]+)([0-9]+)$')


class DeviceInfoBase(ServicePartBase):

    RE_SERIAL_NUMBER = RE_SERIAL_NUMBER
    RE_DISK_NAME = RE_DISK_NAME

    @private
    async def get_serial(self):
        raise NotImplementedError()

    @private
    async def get_disk(self):
        raise NotImplementedError()
