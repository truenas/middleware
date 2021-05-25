import asyncio
import re
import subprocess

from middlewared.service import private, Service
from middlewared.utils import run

RE_CAMCONTROL_APM = re.compile(r'^advanced power management\s+yes', re.M)
RE_CAMCONTROL_POWER = re.compile(r'^power management\s+yes', re.M)


class DiskService(Service):

    @private
    async def power_management_impl(self, dev, disk):
        try:
            identify = (await run('camcontrol', 'identify', dev)).stdout.decode()
        except subprocess.CalledProcessError:
            return

        # Try to set APM
        if RE_CAMCONTROL_APM.search(identify):
            args = ['camcontrol', 'apm', dev]
            if disk['advpowermgmt'] != 'DISABLED':
                args += ['-l', disk['advpowermgmt']]
            asyncio.ensure_future(run(*args, check=False))

        # Try to set idle
        if RE_CAMCONTROL_POWER.search(identify):
            if disk['hddstandby'] != 'ALWAYS ON':
                # database is in minutes, camcontrol uses seconds
                idle = int(disk['hddstandby']) * 60
            else:
                idle = 0

            # We wait a minute before applying idle because its likely happening during system boot
            # or some activity is happening very soon.
            async def camcontrol_idle():
                await asyncio.sleep(60)
                asyncio.ensure_future(run('camcontrol', 'idle', dev, '-t', str(idle), check=False))

            asyncio.ensure_future(camcontrol_idle())
