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

        leave_free_space = parted.sizeToSectors(swap_size_gb, 'GiB', device.sectorSize)
        if data_size is not None:
            min_data_size = parted.sizeToSectors(data_size, 'B', device.sectorSize)
            # Can be increased within the alignment threshold
            max_data_size = parted.sizeToSectors(data_size, 'B', device.sectorSize) + device.optimumAlignment.grainSize
        else:
            min_data_size = parted.sizeToSectors(1, 'GiB', device.sectorSize)
            # Try to give free space for _approximately_ the requested swap size
            max_data_size = parted.sizeToSectors(dd['size'], 'B', device.sectorSize) - leave_free_space
            if max_data_size <= 0:
                raise CallError(f'Disk {disk!r} must be larger than {swap_size_gb} GiB')

        data_geometry = self._get_largest_free_space_region(parted_disk)
        # Place the partition at the end of the disk so the swap is created at the beginning
        start_range = parted.Geometry(
            device,
            data_geometry.start + leave_free_space + device.optimumAlignment.grainSize,
            end=data_geometry.end,
        )
        data_constraint = parted.Constraint(
            startAlign=device.optimumAlignment,
            endAlign=device.optimumAlignment,
            startRange=start_range,
            endRange=data_geometry,
            minSize=min_data_size,
            maxSize=max_data_size,
        )

        def create_data_partition(constraint):
            data_filesystem = parted.FileSystem(type='zfs', geometry=data_geometry)
            data_partition = parted.Partition(
                disk=parted_disk,
                type=parted.PARTITION_NORMAL,
                fs=data_filesystem,
                geometry=data_geometry,
            )
            parted_disk.addPartition(data_partition, constraint=constraint)

        try:
            create_data_partition(data_constraint)
        except parted.PartitionException:
            if data_size is not None:
                # Try to create data partition at the end of the disk, leaving `swap_size_gb` request unsatisfied
                end_range = parted.Geometry(
                    device,
                    data_geometry.end - device.optimumAlignment.grainSize,
                    end=data_geometry.end,
                )
                data_constraint = parted.Constraint(
                    startAlign=device.optimumAlignment,
                    endAlign=device.optimumAlignment,
                    startRange=data_geometry,
                    endRange=end_range,
                    minSize=min_data_size,
                    maxSize=max_data_size,
                )
                try:
                    create_data_partition(data_constraint)
                except parted.PartitionException:
                    raise CallError(f'Disk {disk!r} must be larger than {data_size} bytes')
            else:
                raise CallError(f'Disk {disk!r} must be larger than 1 GiB')

        if swap_size_gb > 0:
            min_swap_size = parted.sizeToSectors(1, 'GiB', device.sectorSize)
            # Select the free space region that we've left previously
            swap_geometries = [
                geometry
                for geometry in parted_disk.getFreeSpaceRegions()
                if geometry.length >= min_swap_size
            ]
            if swap_geometries:
                swap_geometry = swap_geometries[0]
                swap_constraint = parted.Constraint(
                    startAlign=device.optimumAlignment,
                    endAlign=device.optimumAlignment,
                    startRange=swap_geometry,
                    endRange=swap_geometry,
                    minSize=min_swap_size,
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

        # Reorder the partitions so that they logical order matched their physical order
        partitions = parted_disk.partitions[:]
        # Unfortunately this can only be achieved by first removing all partitions (this happens in the RAM, no
        # real disk changes are made yet)
        for partition in partitions:
            parted_disk.removePartition(partition)
        # And then re-creating them in the correct order
        partitions.sort(key=lambda partition: partition.geometry.start)
        for partition in partitions:
            partition.resetNumber()
            constraint = parted.Constraint(exactGeom=partition.geometry)
            geometry = self._get_largest_free_space_region(parted_disk)
            new_partition = parted.Partition(
                disk=parted_disk,
                type=parted.PARTITION_NORMAL,
                fs=parted.FileSystem(type=partition.fileSystem.type, geometry=geometry),
                geometry=geometry,
            )
            parted_disk.addPartition(partition=new_partition, constraint=constraint)

        parted_disk.commit()

        # TODO: Install a dummy boot block so system gives meaningful message if booting from a zpool data disk.

        self.middleware.call_sync('device.settle_udev_events')

        if len(self.middleware.call_sync('disk.list_partitions', disk)) != len(parted_disk.partitions):
            # In some rare cases udev does not re-read the partition table correctly; force it
            self.middleware.call_sync('device.trigger_udev_events', f'/dev/{disk}')
            self.middleware.call_sync('device.settle_udev_events')

    def _get_largest_free_space_region(self, disk):
        return sorted(disk.getFreeSpaceRegions(), key=lambda geometry: geometry.length)[-1]
