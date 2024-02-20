import parted

from middlewared.service import CallError, private, Service


class DiskService(Service):

    @private
    def format(self, disk, swap_size_gb):
        """
        Format a data drive with a maximized data partition
        Rules:
            - The min_data_size is 512MiB
                i.e. the drive must be bigger than 512MiB + 2MiB (partition offsets)
                NOTE: 512MiB is arbitrary, but allows for very small drives
            - If swap_size_gb is not None, then
                * The swap is sized in 1 GiB increments
                * Drive partitioning will abort if requested swap cannot be accomodated
                * A swap partition will be created only if the following is true:
                    swap_size < drive_size - (data_size + partition_gaps)
                * The data partition will be reduced by swap_size_gb
            - The drive is left unchanged if the drive cannot be partitioned according to the rules

        The current config default requested swap is 2 GiB
        A typical drive partition diagram (assuming 1 MiB partition gaps):

        | - unused - | - partition 1 - | - unused -| - partition 2 - | - unused - |
        |------------|-----------------|-----------|-----------------|------------|
        | 1 MiB gap  |   2 GiB swap    | 1 MiB gap |   N GiB data    | 1 MiB gap  |

        """
        if swap_size_gb is not None and (swap_size_gb < 0 or not isinstance(swap_size_gb, int)):
            raise CallError('Requested swap must be a non-negative integer')

        dd = self.middleware.call_sync('device.get_disk', disk)
        if not dd:
            raise CallError(f'Unable to retrieve disk details for {disk!r}')

        if dd['dif']:
            raise CallError(f'Disk: {disk!r} is incorrectly formatted with Data Integrity Feature (DIF).')

        # Get drive specs and size in sectors
        device = parted.getDevice(f'/dev/{disk}')
        drive_size_s = parted.sizeToSectors(dd['size'], 'B', device.sectorSize)

        # Allocate space for the requested swap size
        leave_free_space = parted.sizeToSectors(swap_size_gb, 'GiB', device.sectorSize)

        # Minimum data partition size of 512 MiB is arbitrary
        min_data_size = parted.sizeToSectors(512, 'MiB', device.sectorSize)
        max_data_size = drive_size_s - leave_free_space

        swap_gap = device.optimumAlignment.grainSize if leave_free_space > 0 else 0
        partition_gaps = 2 * device.optimumAlignment.grainSize + swap_gap

        # For validation we should also account for the gaps
        if (max_data_size - partition_gaps) <= 0:
            emsg = f'Disk {disk!r} capacity is too small. Please use a larger capacity drive' + (
                ' or reduce swap.' if leave_free_space > 0 else '.'
            )
            raise CallError(emsg)

        # At this point, the drive has passed validation.  Proceed with drive clean and partitioning
        job = self.middleware.call_sync('disk.wipe', disk, 'QUICK', False)
        job.wait_sync()
        if job.error:
            raise CallError(f'Failed to wipe disk {disk}: {job.error}')

        device.clobber()
        parted_disk = parted.freshDisk(device, 'gpt')

        if max_data_size <= min_data_size:
            max_data_size = min_data_size + device.optimumAlignment.grainSize

        data_geometry = self._get_largest_free_space_region(parted_disk)

        # Place the data partition at the end of the disk. The swap is created at the beginning
        start_range = parted.Geometry(
            device,
            # We need the partition gap _only if_ there is a swap partition
            data_geometry.start + leave_free_space + device.optimumAlignment.grainSize if leave_free_space > 0 else 0,
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
        except parted.PartitionException as e:
            emsg = f'Disk {disk!r} capacity might be too small. Try a larger capacity drive' + (
                ' or reduce swap.' if leave_free_space > 0 else '.'
            )
            raise CallError(f"{emsg}: {e}")

        # If requested, add a swap partition
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
            # Add a human readable name
            if partition.fileSystem.type == 'zfs':
                new_partition.name = 'data'
            elif 'swap' in partition.fileSystem.type:
                new_partition.name = 'swap'

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
