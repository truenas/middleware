import platform

from middlewared.schema import accepts, Dict, Int, Str
from middlewared.service import CallError, private, Service
from middlewared.utils import run

IS_LINUX = platform.system().lower() == 'linux'


class BootService(Service):

    @accepts(
        Str('dev'),
        Dict(
            'options',
            Int('size'),
            Int('swap_size'),
        )
    )
    @private
    async def format(self, dev, options):
        """
        Format a given disk `dev` using the appropriate partition layout
        """
        job = await self.middleware.call('disk.wipe', dev, 'QUICK')
        await job.wait()
        if job.error:
            raise CallError(job.error)

        commands = []
        partitions = []
        if not IS_LINUX:
            commands.append(('gpart', 'create', '-s', 'gpt', '-f', 'active', f'/dev/{dev}'))

        if IS_LINUX:
            zfs_part_no = 4 if options.get('swap_size') else 3
            commands.extend((
                ['sgdisk', '-a1', f'-n1:24K:+1000K', '-t1:EF02', f'/dev/{dev}'],
                ['sgdisk', '-n2:1M:+512M', '-t2:EF00', f'/dev/{dev}'],
                ['sgdisk', f'-n{zfs_part_no}:0:0', f'-t{zfs_part_no}:BF01', f'/dev/{dev}'],
            ))
        else:
            if (await self.middleware.call('boot.get_boot_type')) == 'EFI':
                efi_size = 260
                commands.extend((
                    ['gpart', 'add', '-t', 'efi', '-i', '1', '-s', f'{efi_size}m', dev],
                    ['newfs_msdos', '-F', '16', f'/dev/{dev}p1'],
                ))
                partitions.append(('efi', efi_size * 1024 * 1024))
            else:
                commands.extend((
                    ['gpart', 'add', '-t', 'freebsd-boot', '-i', '1', '-s', '512k', dev],
                    ['gpart', 'set', '-a', 'active', dev],
                ))
                partitions.append(('freebsd-boot', 512 * 1024))

        if options.get('swap_size'):
            if IS_LINUX:
                commands.insert(2, [
                    'sgdisk',
                    f'-n3:514M:+{((int((options["swap_size"] + 127) / 128)) * 128) / 1024 / 1024}M',
                    '-t3:8200', f'/dev/{dev}'
                ])
            else:
                commands.append([
                    'gpart', 'add', '-t', 'freebsd-swap', '-i', '3',
                    '-s', str(options['swap_size']) + 'B', dev
                ])

        if not IS_LINUX:
            commands.append(
                ['gpart', 'add', '-t', 'freebsd-zfs', '-i', '2', '-a', '4k'] + (
                    ['-s', str(options['size']) + 'B'] if options.get('size') else []
                ) + [dev]
            )
        if options.get('size'):
            partitions.append(('freebsd-zfs', options['size']))

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
