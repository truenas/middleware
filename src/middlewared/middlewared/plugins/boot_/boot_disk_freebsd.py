import os
import tempfile

from middlewared.service import CallError, Service
from middlewared.utils import run

from .boot_disk_base import BootDiskBase


class BootService(Service, BootDiskBase):

    async def format(self, dev, options):
        job = await self.middleware.call('disk.wipe', dev, 'QUICK')
        await job.wait()
        if job.error:
            raise CallError(job.error)

        commands = []
        partitions = []
        commands.append(['gpart', 'create', '-s', 'gpt', '-f', 'active', f'/dev/{dev}'])
        boottype = await self.middleware.call('boot.get_boot_type')
        if boottype == 'EFI':
            commands.append(['gpart', 'add', '-t', 'efi', '-i', '1', '-s', '260m', dev])
            partitions.append(("efi", 260 * 1024 * 1024))

            commands.append(['newfs_msdos', '-F', '16', f'/dev/{dev}p1'])
        else:
            commands.append(['gpart', 'add', '-t', 'freebsd-boot', '-i', '1', '-s', '512k', dev])
            partitions.append(('freebsd-boot', 512 * 1024))

            commands.append(['gpart', 'set', '-a', 'active', dev])

        if options.get('swap_size'):
            commands.append([
                'gpart', 'add', '-t', 'freebsd-swap', '-i', '3',
                '-s', str(options['swap_size']) + 'B', dev
            ])

        commands.append(
            ['gpart', 'add', '-t', 'freebsd-zfs', '-i', '2', '-a', '4k'] + (
                ['-s', str(options['size']) + 'B'] if options.get('size') else []
            ) + [dev]
        )
        if options.get("size"):
            partitions.append(("freebsd-zfs", options["size"]))

        try:
            for command in commands:
                p = await run(*command, check=False)
                if p.returncode != 0:
                    raise CallError(
                        '%r failed:\n%s%s' % (' '.join(command), p.stdout.decode('utf-8'), p.stderr.decode('utf-8')))
        except CallError as e:
            if 'gpart: autofill: No space left on device' in e.errmsg:
                diskinfo = {
                    s.split('#')[1].strip(): s.split('#')[0].strip()
                    for s in (await run('/usr/sbin/diskinfo', '-v', dev)).stdout.decode('utf-8').split('\n')
                    if '#' in s
                }
                name = diskinfo.get('Disk descr.', dev)
                size_gb = '%.2f' % ((int(diskinfo['mediasize in sectors']) * int(diskinfo['sectorsize']) /
                                     float(1024 ** 3)))
                size_blocks = '{:,}'.format(int(diskinfo['mediasize in sectors']) * int(diskinfo['sectorsize']) / 512)

                total_partitions_size = sum([p[1] for p in partitions])
                partitions = ['%s, %s blocks' % (p[0], '{:,}'.format(int(p[1] / 512))) for p in partitions]
                partitions.append('total of %s blocks' % '{:,}'.format(int(total_partitions_size / 512)))
                partitions = ', '.join(partitions)

                raise CallError((
                    f'The new device ({name}, {size_gb} GB, {size_blocks} blocks) '
                    f'does not have enough space to to hold the required new partitions ({partitions}). '
                    'New mirrored devices might require more space than existing devices due to changes in the '
                    'booting procedure.'
                ))

            raise

    async def install_loader(self, dev):
        if (await self.middleware.call('boot.get_boot_type')) == 'EFI':
            with tempfile.TemporaryDirectory() as tmpdirname:
                await run('mount', '-t', 'msdosfs', f'/dev/{dev}p1', tmpdirname, check=False)
                try:
                    os.makedirs(f'{tmpdirname}/efi/boot')
                except FileExistsError:
                    pass
                await run('cp', '/boot/boot1.efi', f'{tmpdirname}/efi/boot/BOOTx64.efi', check=False)
                await run('umount', tmpdirname, check=False)

        else:
            await run(
                'gpart', 'bootcode', '-b', '/boot/pmbr', '-p', '/boot/gptzfsboot', '-i', '1', f'/dev/{dev}',
                check=False
            )
