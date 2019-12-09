import asyncio
import os
import platform
import re
import signal
import subprocess

from middlewared.service import Service
from middlewared.utils import Popen, run

from .wipe_base import WipeDiskBase


RE_DD = re.compile(r'^(\d+) bytes transferred .*\((\d+) bytes')


class DiskService(Service, WipeDiskBase):
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

    async def wipe(self, job, dev, mode, sync):
        await self.middleware.call('disk.swaps_remove_disks', [dev])

        # FIXME: Please implement removal from graid for linux
        if platform.platform().lower() != 'linux':
            await self.middleware.call('disk.remove_disk_from_graid', dev)

        # First do a quick wipe of every partition to clean things like zfs labels
        if mode == 'QUICK':
            for part in await self.middleware.call('device.list_partitions'):
                await self.wipe_quick(part['name'], part['size'])

        await run('gpart', 'destroy', '-F', f'/dev/{dev}', check=False)

        # Wipe out the partition table by doing an additional iterate of create/destroy
        await run('gpart', 'create', '-s', 'gpt', f'/dev/{dev}')
        await run('gpart', 'destroy', '-F', f'/dev/{dev}')

        if mode == 'QUICK':
            await self.middleware.call('disk.wipe_quick', dev)
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
