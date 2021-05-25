import asyncio

from middlewared.service import private, Service
from middlewared.utils import run


class DiskService(Service):

    @private
    async def power_management_impl(self, dev, disk):
        asyncio.ensure_future(run(
            'hdparm', '-B', disk['advpowermgmt'] if disk['advpowermgmt'] != 'DISABLED' else '255', f'/dev/{dev}',
            check=False,
        ))

        if disk['hddstandby'] != 'ALWAYS ON':
            if int(disk['hddstandby']) <= 20:
                # Values from 1 to 240 specify multiples of 5 seconds
                idle = int(int(disk['hddstandby']) * 60 / 5)
            else:
                # values from 241 to 251 specify multiples of 30 minutes.
                idle = 240 + int(int(disk['hddstandby']) / 30)
        else:
            idle = 0

        # We wait a minute before applying idle because its likely happening during system boot
        # or some activity is happening very soon.
        async def camcontrol_idle():
            await asyncio.sleep(60)
            asyncio.ensure_future(run('hdparm', '-S', str(idle), f'/dev/{dev}', check=False))

        asyncio.ensure_future(camcontrol_idle())
