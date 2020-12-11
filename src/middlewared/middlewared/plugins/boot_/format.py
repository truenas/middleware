from middlewared.schema import accepts, Dict, Int, Str
from middlewared.service import CallError, private, Service
from middlewared.utils import osc, run


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
        if not disk_details:
            raise CallError(f'Details for {dev} not found.')

        swap_size = options.get('swap_size')
        commands = []
        partitions = []
        efi_boot = (await self.middleware.call('boot.get_boot_type')) == 'EFI'
        if osc.IS_FREEBSD:
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
        else:
            partitions.extend([
                ('BIOS boot partition', 1048576),  # We allot 1MiB to bios boot partition
                ('EFI System', 536870912)   # We allot 512MiB for EFI partition
            ])
            if swap_size:
                partitions.append(('Linux swap', swap_size))
            if options.get('size'):
                partitions.append(('Solaris /usr & Mac ZFS', options['size']))

        # Around 80 sectors are reserved by Linux/FreeBSD for GPT tables and
        # our 4096 bytes alignment offset for the boot disk
        partitions.append((
            'GPT partition table', (73 if osc.IS_LINUX else 80) * disk_details['sectorsize']
        ))
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

        if osc.IS_LINUX:
            zfs_part_size = f'+{int(options["size"]/1024)}K' if options.get('size') else 0
            commands.extend((
                ['sgdisk', f'-a{int(4096/disk_details["sectorsize"])}', f'-n1:0:+1024K', '-t1:EF02', f'/dev/{dev}'],
                ['sgdisk', '-n2:0:+524288K', '-t2:EF00', f'/dev/{dev}'],
                ['sgdisk', f'-n3:0:{zfs_part_size}', f'-t3:BF01', f'/dev/{dev}'],
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

        if swap_size:
            if osc.IS_LINUX:
                commands.insert(2, [
                    'sgdisk',
                    f'-n4:0:+{int(swap_size / 1024)}K',
                    '-t4:8200', f'/dev/{dev}'
                ])
            else:
                commands.append([
                    'gpart', 'add', '-t', 'freebsd-swap', '-i', '3',
                    '-s', str(options['swap_size']) + 'B', dev
                ])

        if osc.IS_FREEBSD:
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

        if osc.IS_LINUX:
            await self.middleware.call('device.settle_udev_events')
