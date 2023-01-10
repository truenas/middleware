import parted

from middlewared.service import CallError, private, Service


class DiskService(Service):

    @private
    def format(self, disk, data_size, swap_size_gb):
        dd = self.middleware.call_sync('device.get_disk', disk)
        if not dd:
            raise CallError(f'Unable to retrieve disk details for {disk!r}')

        if dd['dif']:
            raise CallError(f'Disk: {disk!r} is incorrectly formatted with Data Integrity Feature (DIF).')

        job = self.middleware.call_sync('disk.wipe', disk, 'QUICK', False)
        job.wait_sync()
        if job.error:
            raise CallError(f'Failed to wipe disk {disk}: {job.error}')

        device = parted.getDevice(f'/dev/{disk}')
        device.clobber()
        parted_disk = parted.freshDisk(device, 'gpt')

        if data_size is not None:
            data_geometry = self._get_largest_free_space_region(parted_disk)
            data_constraint = parted.Constraint(
                startAlign=device.optimumAlignment,
                endAlign=device.optimumAlignment,
                startRange=data_geometry,
                endRange=data_geometry,
                minSize=parted.sizeToSectors(data_size, 'B', device.sectorSize),
                # Can be increased within the alignment threshold
                maxSize=parted.sizeToSectors(data_size, 'B', device.sectorSize) + device.optimumAlignment.grainSize,
            )
            data_filesystem = parted.FileSystem(type='zfs', geometry=data_geometry)
            data_partition = parted.Partition(
                disk=parted_disk,
                type=parted.PARTITION_NORMAL,
                fs=data_filesystem,
                geometry=data_geometry,
            )
            try:
                parted_disk.addPartition(data_partition, constraint=data_constraint)
            except parted.PartitionException:
                raise CallError(f'Disk {disk!r} must be larger than {data_size} bytes')

        if swap_size_gb > 0:
            swap_geometry = self._get_largest_free_space_region(parted_disk)
            swap_constraint = parted.Constraint(
                startAlign=device.optimumAlignment,
                endAlign=device.optimumAlignment,
                startRange=swap_geometry,
                endRange=swap_geometry,
                minSize=parted.sizeToSectors(1, 'GiB', device.sectorSize),
                maxSize=(
                    parted.sizeToSectors(swap_size_gb, 'GiB', device.sectorSize) + device.optimumAlignment.grainSize
                ),
            )
            swap_filesystem = parted.FileSystem(type='linux-swap(v1)', geometry=swap_geometry)
            swap_partition = parted.Partition(
                disk=parted_disk,
                type=parted.PARTITION_NORMAL,
                fs=swap_filesystem,
                geometry=swap_geometry,
            )
            try:
                parted_disk.addPartition(swap_partition, constraint=swap_constraint)
            except parted.PartitionException as e:
                self.logger.warning('Unable to fit a swap partition on disk %r: %r', disk, e)

        if data_size is None:
            data_geometry = self._get_largest_free_space_region(parted_disk)
            data_constraint = device.optimalAlignedConstraint
            data_filesystem = parted.FileSystem(type='zfs', geometry=data_geometry)
            data_partition = parted.Partition(
                disk=parted_disk,
                type=parted.PARTITION_NORMAL,
                fs=data_filesystem,
                geometry=data_geometry,
            )
            try:
                parted_disk.addPartition(data_partition, constraint=data_constraint)
            except parted.PartitionException:
                if swap_size_gb > 0:
                    # If we are unable to fit any data partition on a disk, that might mean that the swap that was
                    # created was too large
                    raise CallError(f'Disk {disk!r} must be larger than {swap_size_gb} GiB')

                raise

        parted_disk.commit()

        # TODO: Install a dummy boot block so system gives meaningful message if booting from a zpool data disk.

        self.middleware.call_sync('device.settle_udev_events')

        if len(self.middleware.call_sync('disk.list_partitions', disk)) != len(parted_disk.partitions):
            # In some rare cases udev does not re-read the partition table correctly; force it
            self.middleware.call_sync('device.trigger_udev_events', f'/dev/{disk}')
            self.middleware.call_sync('device.settle_udev_events')

    def _get_largest_free_space_region(self, disk):
        return sorted(disk.getFreeSpaceRegions(), key=lambda geometry: geometry.length)[-1]
