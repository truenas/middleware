import pathlib

import parted

from middlewared.service import CallError, private, Service


class DiskService(Service):

    @private
    def format(self, disk, swap_size_gb=None):
        """
        Format a data drive with a maximized data partition
        Rules:
            - The min_data_size is 512MiB
                i.e. the drive must be bigger than 512MiB + 2MiB (partition offsets)
                NOTE: 512MiB is arbitrary, but allows for very small drives
            - The drive is left unchanged if the drive cannot be partitioned according to the rules

        A typical drive partition diagram (assuming 1 MiB partition gaps):

        | - unused - | - partition 1 - | - unused -|
        |------------|-----------------|-----------|
        | 1 MiB gap  |   N GiB data    | 1 MiB gap |
        """
        sysfs = pathlib.Path('/sys/class/block/{disk}')
        if not sysfs.exists():
            raise CallError(f'Unable to retrieve disk details for {disk!r}')

        is_dif = next(sysfs.glob('device/scsi_disk/*/protection_type'), None)
        if is_dif is not None and is_dif.read_text().strip() != '0':
            # 0 == disabled, > 0 enabled
            raise CallError(f'Disk: {disk!r} is incorrectly formatted with Data Integrity Feature (DIF).')

        device = parted.getDevice(f'/dev/{disk}')
        if device.optimumAlignment.grainSize <= 0:
            # We rely on a valid 'grainSize', let's make sure before we proceed.
            raise CallError(f'Unable to format {disk!r}: grainSize = {device.optimumAlignment.grainSize}')

        drive_size_s = parted.sizeToSectors(device.getSize('B'), 'B', device.sectorSize)
        partition_gaps = 2 * device.optimumAlignment.grainSize

        # Minimum data partition size of 512 MiB is arbitrary
        min_data_size = parted.sizeToSectors(512, 'MiB', device.sectorSize)
        # Here we leave max_data_size possibly oversized to allow for parted
        # to create the maximal sized partition
        max_data_size = drive_size_s

        # For validation we should also account for the gaps
        if (max_data_size - partition_gaps) <= 0:
            raise CallError(f'Disk {disk!r} capacity is too small. Please use a larger capacity drive.')

        # At this point, the drive has passed validation.  Proceed with drive clean and partitioning
        job = self.middleware.call_sync('disk.wipe', disk, 'QUICK', False)
        job.wait_sync()
        if job.error:
            raise CallError(f'Failed to wipe disk {disk}: {job.error}')

        device.clobber()
        parted_disk = parted.freshDisk(device, 'gpt')

        # Sanity: make sure max is larger than min
        if max_data_size <= min_data_size:
            max_data_size = min_data_size + device.optimumAlignment.grainSize

        data_geometry = self._get_largest_free_space_region(parted_disk)
        start_range = parted.Geometry(
            device,
            data_geometry.start,
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
            raise CallError(f'Failed to create data partition on {disk!r}: {e}')

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
