import re

from middlewared.service import private, ServicePartBase

RE_SERIAL_NUMBER = re.compile(r'Serial Number:\s+(?P<serial>.+)', re.I)


class DeviceInfoBase(ServicePartBase):

    RE_SERIAL_NUMBER = RE_SERIAL_NUMBER

    @private
    async def get_serial(self):
        raise NotImplementedError()

    @private
    async def get_disk(self):
        raise NotImplementedError()
