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

        disk_details = await self.middleware.call('device.get_disk', dev)
        if not disk_details['name']:
            raise CallError(f'Details for {disk_details["name"]} not found.')

        commands = []
        partitions = []
        efi_boot = (await self.middleware.call('boot.get_boot_type')) == 'EFI'
        if not IS_LINUX:
            commands.append(('gpart', 'create', '-s', 'gpt', '-f', 'active', f'/dev/{dev}'))
            partitions.append(
                ('efi' if efi_boot else 'freebsd-boot', 272629760 if efi_boot else 524288),
            )
            if options.get('swap_size'):
                partitions.append(('freebsd-swap', options['swap_size']))
            if options.get('size'):
                partitions.append(('freebsd-zfs', options['size']))
        else:
            partitions.extend([
                ('BIOS boot partition', 1048576),
                ('EFI System', 536870912)
            ])
            if options.get('swap_size'):
                partitions.append(('Linux swap', ((int((options['swap_size'] + 127) / 128)) * 128)))
            if options.get('size'):
                partitions.append(('Solaris /usr & Mac ZFS', options['size']))

        total_partition_size = sum(map(lambda y: y[1], partitions))
        if disk_details['size'] < total_partition_size:
            partitions = [
                '%s, %s blocks' % (p[0], '{:,}'.format(int(p[1] / disk_details['sectorsize']))) for p in partitions
            ]
            partitions.append(
                'total of %s blocks' % '{:,}'.format(int(total_partition_size / disk_details['sectorsize']))
            )
            raise CallError(
                f'The new device ({dev}, {disk_details["size"]} GB, {disk_details["blocks"]} blocks) '
                f'does not have enough space to to hold the required new partitions ({", ".join(partitions)}). '
                'New mirrored devices might require more space than existing devices due to changes in the '
                'booting procedure.'
            )

        if IS_LINUX:
            zfs_part_no = 4 if options.get('swap_size') else 3
            zfs_part_size = f'{int(options["size"]/1024)}K' if options.get('size') else 0
            commands.extend((
                ['sgdisk', '-a1', f'-n1:24K:+1000K', '-t1:EF02', f'/dev/{dev}'],
                ['sgdisk', '-n2:1024K:+524288K', '-t2:EF00', f'/dev/{dev}'],
                ['sgdisk', f'-n{zfs_part_no}:0:{zfs_part_size}', f'-t{zfs_part_no}:BF01', f'/dev/{dev}'],
            ))
        else:
            if efi_boot:
                efi_size = 260
                commands.extend((
                    ['gpart', 'add', '-t', 'efi', '-i', '1', '-s', f'{efi_size}m', dev],
                    ['newfs_msdos', '-F', '16', f'/dev/{dev}p1'],
                ))
            else:
                commands.extend((
                    ['gpart', 'add', '-t', 'freebsd-boot', '-i', '1', '-s', '512k', dev],
                    ['gpart', 'set', '-a', 'active', dev],
                ))

        if options.get('swap_size'):
            if IS_LINUX:
                commands.insert(2, [
                    'sgdisk',
                    f'-n3:525312K:+{int(((int((options["swap_size"] + 127) / 128)) * 128) / 1024)}K',
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

        for command in commands:
            p = await run(*command, check=False)
            if p.returncode != 0:
                raise CallError(
                    '%r failed:\n%s%s' % (' '.join(command), p.stdout.decode('utf-8'), p.stderr.decode('utf-8'))
                )
