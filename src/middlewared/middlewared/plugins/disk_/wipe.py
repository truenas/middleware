import asyncio
import os
import platform
import re
import signal
import subprocess

from middlewared.schema import accepts, Bool, Str
from middlewared.service import job, private, Service
from middlewared.utils import Popen, run


RE_DD = re.compile(r'^(\d+) bytes transferred .*\((\d+) bytes')


class DiskService(Service):
    @private
    async def wipe_quick(self, dev, size=None):
        # If the size is too small, lets just skip it for now.
        # In the future we can adjust dd size
        if size and size < 33554432:
            return
        await run('dd', 'if=/dev/zero', f'of=/dev/{dev}', 'bs=1m', 'count=32')
        size = await self.middleware.call('device.get_dev_size', dev)
        if not size:
            self.logger.error(f'Unable to determine size of {dev}')
        else:
            # This will fail when EOL is reached
            await run('dd', 'if=/dev/zero', f'of=/dev/{dev}', 'bs=1m', f'oseek={int(size / 1024) - 32}', check=False)

    @accepts(
        Str('dev'),
        Str('mode', enum=['QUICK', 'FULL', 'FULL_RANDOM']),
        Bool('synccache', default=True),
    )
    @job(lock=lambda args: args[0])
    async def wipe(self, job, dev, mode, sync):
        """
        Performs a wipe of a disk `dev`.
        It can be of the following modes:
          - QUICK: clean the first few and last megabytes of every partition and disk
          - FULL: write whole disk with zero's
          - FULL_RANDOM: write whole disk with random bytes
        """
        # FIXME: Please implement removal from graid for linux and removal of disk from swap
        if platform.platform().lower() != 'linux':
            await self.middleware.call('disk.swaps_remove_disks', [dev])
            await self.middleware.call('disk.remove_disk_from_graid', dev)

        # First do a quick wipe of every partition to clean things like zfs labels
        if mode == 'QUICK':
            for part in await self.middleware.call('device.list_partitions', dev):
                await self.wipe_quick(part['name'], part['size'])

        await self.middleware.call('disk.destroy_partitions', dev)

        if mode == 'QUICK':
            await self.wipe_quick(dev)
        else:
            size = await self.middleware.call('device.get_dev_size', dev) or 1

            proc = await Popen([
                'dd',
                'if=/dev/{}'.format('zero' if mode == 'FULL' else 'random'),
                f'of=/dev/{dev}',
                'bs=1m',
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            async def dd_wait():
                while True:
                    if proc.returncode is not None:
                        break
                    os.kill(proc.pid, signal.SIGINFO)
                    await asyncio.sleep(1)

            asyncio.ensure_future(dd_wait())

            while True:
                line = await proc.stderr.readline()
                if line == b'':
                    break
                line = line.decode()
                reg = RE_DD.search(line)
                if reg:
                    job.set_progress((int(reg.group(1)) / size) * 100, extra={'speed': int(reg.group(2))})

        if sync:
            await self.middleware.call('disk.sync', dev)
