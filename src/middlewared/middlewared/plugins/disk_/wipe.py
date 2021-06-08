import asyncio
import os
import re
import signal
import subprocess

from middlewared.schema import accepts, Bool, Ref, returns, Str
from middlewared.service import CallError, job, private, Service
from middlewared.utils import osc, Popen, run


if osc.IS_LINUX:
    RE_DD = re.compile(r'^(\d+).*bytes.*copied.*, ([\d\.]+)\s*(GB|MB|KB|B)/s')
else:
    RE_DD = re.compile(r'^(\d+) bytes transferred .*\((\d+) bytes')


class DiskService(Service):

    @private
    async def destroy_partitions(self, disk):
        if osc.IS_LINUX:
            cp = await run(['sgdisk', '-Z', os.path.join('/dev', disk)], check=False)
            if not (
                not cp.returncode or (
                    cp.returncode == 2 and 'gpt data structures destroyed!' in cp.stdout.decode().lower()
                )
            ):
                # We have return code 2 when sgdisk is unable to read partition table, which is fine in our case
                # as we want to destroy the partition table anyways
                raise CallError(f'Failed to wipe {disk}: {cp.stderr.decode()}')
        else:
            await run('gpart', 'destroy', '-F', f'/dev/{disk}', check=False)
            # Wipe out the partition table by doing an additional iterate of create/destroy
            await run('gpart', 'create', '-s', 'gpt', f'/dev/{disk}')
            await run('gpart', 'destroy', '-F', f'/dev/{disk}')

    @private
    async def wipe_quick(self, dev, size=None):
        # If the size is too small, lets just skip it for now.
        # In the future we can adjust dd size
        if size and size < 33554432:
            return
        await run('dd', 'if=/dev/zero', f'of=/dev/{dev}', 'bs=1M', 'count=32')
        size = await self.middleware.call('disk.get_dev_size', dev)
        if not size:
            self.logger.error(f'Unable to determine size of {dev}')
        else:
            # This will fail when EOL is reached
            await run(
                'dd', 'if=/dev/zero', f'of=/dev/{dev}', 'bs=1M', f'oseek={int(size / (1024*1024)) - 32}', check=False
            )

    @accepts(
        Str('dev'),
        Str('mode', enum=['QUICK', 'FULL', 'FULL_RANDOM'], required=True),
        Bool('synccache', default=True),
        Ref('swap_removal_options'),
    )
    @returns()
    @job(
        lock=lambda args: args[0],
        description=lambda dev, mode, *args: f'{mode.replace("_", " ").title()} wipe of disk {dev}',
        abortable=True,
    )
    async def wipe(self, job, dev, mode, sync, options):
        """
        Performs a wipe of a disk `dev`.
        It can be of the following modes:
          - QUICK: clean the first few and last megabytes of every partition and disk
          - FULL: write whole disk with zero's
          - FULL_RANDOM: write whole disk with random bytes
        """
        await self.middleware.call('disk.swaps_remove_disks', [dev], options)

        if osc.IS_FREEBSD:
            await self.middleware.call('disk.remove_disk_from_graid', dev)

        # First do a quick wipe of every partition to clean things like zfs labels
        if mode == 'QUICK':
            for part in await self.middleware.call('disk.list_partitions', dev):
                await self.wipe_quick(part['name'], part['size'])

        await self.middleware.call('disk.destroy_partitions', dev)

        if mode == 'QUICK':
            await self.wipe_quick(dev)
        else:
            size = await self.middleware.call('disk.get_dev_size', dev) or 1

            proc = await Popen([
                'dd',
                'if=/dev/{}'.format('zero' if mode == 'FULL' else 'random'),
                f'of=/dev/{dev}',
                'bs=1M',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

            try:
                async def dd_wait():
                    while True:
                        if proc.returncode is not None:
                            break
                        os.kill(proc.pid, signal.SIGUSR1 if osc.IS_LINUX else signal.SIGINFO)
                        await asyncio.sleep(1)

                asyncio.ensure_future(dd_wait())

                while True:
                    line = await proc.stderr.readline()
                    if line == b'':
                        break
                    line = line.decode()
                    reg = RE_DD.search(line)
                    if reg:
                        speed = float(reg.group(2)) if osc.IS_LINUX else int(reg.group(2))
                        if osc.IS_LINUX:
                            mapping = {'gb': 1024 * 1024 * 1024, 'mb': 1024 * 1024, 'kb': 1024, 'b': 1}
                            speed = int(speed * mapping[reg.group(3).lower()])
                        job.set_progress((int(reg.group(1)) / size) * 100, extra={'speed': speed})
            except asyncio.CancelledError:
                proc.kill()
                raise

        if sync:
            await self.middleware.call('disk.sync', dev)
