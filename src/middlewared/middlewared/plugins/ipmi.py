from bsd import kld

from middlewared.schema import Bool, Dict, Int, accepts
from middlewared.service import CallError, Service
from middlewared.utils import run

import errno
import os
import subprocess

channels = []


class IPMIService(Service):

    @accepts()
    async def is_loaded(self):
        return os.path.exists('/dev/ipmi0')

    @accepts()
    async def channels(self):
        """
        Return a list with the IPMI channels available.
        """
        return channels

    @accepts(Dict(
        'options',
        Int('seconds'),
        Bool('force'),
    ))
    async def identify(self, options=None):
        """
        Turn on IPMI chassis identify light.

        To turn off specify 0 as `seconds`.
        """
        options = options or {}
        if options.get('force') and options.get('seconds'):
            raise CallError('You have to use either "seconds" or "force" option, not both')

        if options.get('force'):
            cmd = 'force'
        else:
            cmd = str(options.get('seconds'))
        await run('ipmitool', 'chassis', 'identify', cmd)


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
