from middlewared.schema import accepts, Dict, Int, Str
from middlewared.service import CallError, private, Service
from middlewared.utils import run


class BootService(Service):

    @accepts(
        Str('dev'),
        Dict(
            'options',
            Int('size'),
            Str('legacy_schema', enum=[None, 'BIOS_ONLY', 'EFI_ONLY'], null=True, default=None),
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

        commands = []
        partitions = []
        if options['legacy_schema'] == 'BIOS_ONLY':
            partitions.extend([
                ('BIOS boot partition', 524288),
            ])
        elif options['legacy_schema'] == 'EFI_ONLY':
            partitions.extend([
                ('EFI System', 272629760),
            ])
        else:
            partitions.extend([
                ('BIOS boot partition', 1048576),  # We allot 1MiB to bios boot partition
                ('EFI System', 536870912)   # We allot 512MiB for EFI partition
            ])
        if options.get('size'):
            partitions.append(('Solaris /usr & Mac ZFS', options['size']))

        # 73 sectors are reserved by Linux for GPT tables and
        # our 4096 bytes alignment offset for the boot disk
        partitions.append((
            'GPT partition table', 73 * disk_details['sectorsize']
        ))
        total_partition_size = sum(map(lambda y: y[1], partitions))
        if disk_details['size'] < total_partition_size:
            partitions = [
                '%s: %s blocks' % (p[0], '{:,}'.format(p[1] // disk_details['sectorsize'])) for p in partitions
            ]
            partitions.append(
                'total of %s blocks' % '{:,}'.format(total_partition_size // disk_details['sectorsize'])
            )
            disk_blocks = '{:,}'.format(disk_details["blocks"])
            raise CallError(
                f'The new device ({dev}, {disk_details["size"] / (1024 ** 3)} GB, {disk_blocks} blocks) '
                f'does not have enough space to to hold the required new partitions ({", ".join(partitions)}). '
                'New mirrored devices might require more space than existing devices due to changes in the '
                'booting procedure.'
            )

        zfs_part_size = f'+{options["size"] // 1024}K' if options.get('size') else 0
        if options['legacy_schema']:
            if options['legacy_schema'] == 'BIOS_ONLY':
                commands.extend((
                    ['sgdisk', f'-a{4096 // disk_details["sectorsize"]}', '-n1:0:+512K', '-t1:EF02', f'/dev/{dev}'],
                ))
            elif options['legacy_schema'] == 'EFI_ONLY':
                commands.extend((
                    ['sgdisk', f'-a{4096 // disk_details["sectorsize"]}', '-n1:0:+260M', '-t1:EF00', f'/dev/{dev}'],
                ))

            # Creating standard-size partitions first leads to better alignment and more compact disk usage
            # and can help to fit larger data partition.
            commands.extend([
                ['sgdisk', f'-n2:0:{zfs_part_size}', '-t2:BF01', f'/dev/{dev}'],
            ])
        else:
            commands.extend((
                ['sgdisk', f'-a{4096 // disk_details["sectorsize"]}', '-n1:0:+1024K', '-t1:EF02', f'/dev/{dev}'],
                ['sgdisk', '-n2:0:+524288K', '-t2:EF00', f'/dev/{dev}'],
            ))

            # Creating standard-size partitions first leads to better alignment and more compact disk usage
            # and can help to fit larger data partition.
            commands.extend([
                ['sgdisk', f'-n3:0:{zfs_part_size}', '-t3:BF01', f'/dev/{dev}']
            ])

        for command in commands:
            p = await run(*command, check=False)
            if p.returncode != 0:
                raise CallError(
                    '{} failed:\n{}{}'.format(' '.join(command), p.stdout.decode('utf-8'), p.stderr.decode('utf-8'))
                )

        await self.middleware.call('device.settle_udev_events')
