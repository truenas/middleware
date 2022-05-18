from middlewared.schema import accepts, Dict, Int, Str
from middlewared.service import CallError, private, Service
from middlewared.utils import run


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
        await job.wait(raise_error=True)

        disk_details = await self.middleware.call('device.get_disk', dev)
        if not disk_details:
            raise CallError(f'Details for {dev} not found.')

        swap_size = options.get('swap_size')
        commands = []
        partitions = []
        efi_boot = (await self.middleware.call('boot.get_boot_type')) == 'EFI'
        commands.append(('gpart', 'create', '-s', 'gpt', '-f', 'active', f'/dev/{dev}'))
        # 272629760 bytes ( 260 mb ) are required by FreeBSD
        # for EFI partition and 524288 bytes ( 512kb ) if it's bios
        partitions.append(
            ('efi' if efi_boot else 'freebsd-boot', 272629760 if efi_boot else 524288),
        )
        if options.get('swap_size'):
            partitions.append(('freebsd-swap', options['swap_size']))
        if options.get('size'):
            partitions.append(('freebsd-zfs', options['size']))

        # Around 80 sectors are reserved by FreeBSD for GPT tables and
        # our 4096 bytes alignment offset for the boot disk
        partitions.append(('GPT partition table', 80 * disk_details['sectorsize']))
        total_partition_size = sum(map(lambda y: y[1], partitions))
        if disk_details['size'] < total_partition_size:
            partitions = [
                '%s, %s blocks' % (p[0], '{:,}'.format(int(p[1] / disk_details['sectorsize']))) for p in partitions
            ]
            partitions.append(
                'total of %s blocks' % '{:,}'.format(int(total_partition_size / disk_details['sectorsize']))
            )
            raise CallError(
                f'The new device ({dev}, {disk_details["size"]/(1024**3)} GB, {disk_details["blocks"]} blocks) '
                f'does not have enough space to to hold the required new partitions ({", ".join(partitions)}). '
                'New mirrored devices might require more space than existing devices due to changes in the '
                'booting procedure.'
            )

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

        if swap_size:
            commands.append([
                'gpart', 'add', '-t', 'freebsd-swap', '-i', '3',
                '-s', str(options['swap_size']) + 'B', dev
            ])

        commands.append(
            ['gpart', 'add', '-t', 'freebsd-zfs', '-i', '2', '-a', '4k'] + (
                ['-s', str(options['size']) + 'B'] if options.get('size') else []
            ) + [dev]
        )

        for command in commands:
            p = await run(*command, check=False)
            if p.returncode != 0:
                raise CallError(
                    '{} failed:\n{}{}'.format(' '.join(command), p.stdout.decode('utf-8'), p.stderr.decode('utf-8'))
                )

        await self.middleware.call('geom.cache.invalidate')
