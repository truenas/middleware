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
        await job.wait()
        if job.error:
            raise CallError(job.error)

        disk_details = await self.middleware.call('device.get_disk', dev)
        if not disk_details:
            raise CallError(f'Details for {dev} not found.')

        swap_size = options.get('swap_size')
        commands = []
        partitions = []
        partitions.extend([
            ('BIOS boot partition', 1048576),  # We allot 1MiB to bios boot partition
            ('EFI System', 536870912)   # We allot 512MiB for EFI partition
        ])
        if swap_size:
            partitions.append(('Linux swap', swap_size))
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

        zfs_part_size = f'+{int(options["size"]/1024)}K' if options.get('size') else 0
        commands.extend((
            ['sgdisk', f'-a{int(4096/disk_details["sectorsize"])}', f'-n1:0:+1024K', '-t1:EF02', f'/dev/{dev}'],
            ['sgdisk', '-n2:0:+524288K', '-t2:EF00', f'/dev/{dev}'],
            ['sgdisk', f'-n3:0:{zfs_part_size}', f'-t3:BF01', f'/dev/{dev}'],
        ))

        if swap_size:
            commands.insert(2, [
                'sgdisk',
                f'-n4:0:+{int(swap_size / 1024)}K',
                '-t4:8200', f'/dev/{dev}'
            ])

        for command in commands:
            p = await run(*command, check=False)
            if p.returncode != 0:
                raise CallError(
                    '{} failed:\n{}{}'.format(' '.join(command), p.stdout.decode('utf-8'), p.stderr.decode('utf-8'))
                )

        await self.middleware.call('device.settle_udev_events')
