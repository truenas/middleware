import asyncio
import os
import re
import signal
import subprocess

from bsd import geom

from middlewared.schema import accepts, Bool, Str
from middlewared.service import job, private, Service
from middlewared.utils import Popen, run


RE_DD = re.compile(r'^(\d+) bytes transferred .*\((\d+) bytes')


class DiskService(Service):
    @private
    async def wipe_quick(self, dev, size=None):
        """
        Perform a quick wipe of a disk `dev` by the first few and last few megabytes
        """
        # If the size is too small, lets just skip it for now.
        # In the future we can adjust dd size
        if size and size < 33554432:
            return
        await run('dd', 'if=/dev/zero', f'of=/dev/{dev}', 'bs=1m', 'count=32')
        try:
            cp = await run('diskinfo', dev)
            size = int(int(re.sub(r'\s+', ' ', cp.stdout.decode()).split()[2]) / 1024)
        except subprocess.CalledProcessError:
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
        await self.middleware.call('disk.swaps_remove_disks', [dev])

        # Its possible a disk was previously used by graid so we need to make sure to
        # remove the disk from it (#40560)
        gdisk = geom.class_by_name('DISK')
        graid = geom.class_by_name('RAID')
        if gdisk and graid:
            prov = gdisk.xml.find(f'.//provider[name = "{dev}"]')
            if prov is not None:
                provid = prov.attrib.get('id')
                graid = graid.xml.find(f'.//consumer/provider[@ref = "{provid}"]/../../name')
                if graid is not None:
                    cp = await run('graid', 'remove', graid.text, dev, check=False)
                    if cp.returncode != 0:
                        self.logger.debug(
                            'Failed to remove %s from %s: %s', dev, graid.text, cp.stderr.decode()
                        )

        # First do a quick wipe of every partition to clean things like zfs labels
        if mode == 'QUICK':
            await self.middleware.run_in_thread(geom.scan)
            klass = geom.class_by_name('PART')
            for g in klass.xml.findall(f'./geom[name=\'{dev}\']'):
                for p in g.findall('./provider'):
                    size = p.find('./mediasize')
                    if size is not None:
                        try:
                            size = int(size.text)
                        except ValueError:
                            size = None
                    name = p.find('./name')
                    await self.middleware.call('disk.wipe_quick', name.text, size)

        await run('gpart', 'destroy', '-F', f'/dev/{dev}', check=False)

        # Wipe out the partition table by doing an additional iterate of create/destroy
        await run('gpart', 'create', '-s', 'gpt', f'/dev/{dev}')
        await run('gpart', 'destroy', '-F', f'/dev/{dev}')

        if mode == 'QUICK':
            await self.middleware.call('disk.wipe_quick', dev)
        else:
            cp = await run('diskinfo', dev)
            size = int(re.sub(r'\s+', ' ', cp.stdout.decode()).split()[2])

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
