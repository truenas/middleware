from bsd import kld

from middlewared.schema import Dict, List, Str, accepts
from middlewared.service import CallError, Service
from middlewared.utils import run

import errno
import subprocess

channels = []


class IPMIService(Service):

    @accepts()
    async def channels(self):
        """
        Return a list with the IPMI channels available.
        """
        return channels


async def setup(middleware):

    try:
        kld.kldload('/boot/kernel/ipmi.ko')
    except OSError as e:
        # Only skip if not already loaded
        if e.errno != errno.EEXIST:
            middleware.logger.warn(f'Cannot load IPMI module: {e}')
            return

    # Scan available channels
    for i in range(1, 17):
        try:
            await run('/usr/local/bin/ipmitool', 'lan', 'print', str(i))
        except subprocess.CalledProcessError:
            continue
        channels.append(i)
