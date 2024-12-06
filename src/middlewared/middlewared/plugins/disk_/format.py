import pathlib

import parted

from middlewared.service import CallError, private, Service


class DiskService(Service):

    @private
    def format(self, disk):
        """Format a data drive with a maximized data partition"""
        sysfs = pathlib.Path(f'/sys/class/block/{disk}')
        if not sysfs.exists():
            raise CallError(f'Unable to retrieve disk details for {disk!r}')

        is_dif = next(sysfs.glob('device/scsi_disk/*/protection_type'), None)
        if is_dif is not None and is_dif.read_text().strip() != '0':
            # 0 == disabled, > 0 enabled
            raise CallError(f'Disk: {disk!r} is incorrectly formatted with Data Integrity Feature (DIF).')

        # wipe the disk (quickly) of any existing filesystems
        self.middleware.call_sync('disk.wipe', disk, 'QUICK', False).wait_sync(raise_error=True)

        dev = parted.getDevice(f'/dev/{disk}')
        parted_disk = parted.freshDisk(dev, 'gpt')
        regions = sorted(parted_disk.getFreeSpaceRegions(), key=lambda x: x.length)[-1]
        geom = parted.Geometry(start=regions.start, end=regions.end, device=dev)
        fs = parted.FileSystem(type='zfs', geometry=geom)
        part = parted.Partition(disk=parted_disk, type=parted.PARTITION_NORMAL, fs=fs, geometry=geom)
        part.name = 'data'  # give a human readable name to the label
        parted_disk.addPartition(part, constraint=dev.optimalAlignedConstraint)
        parted_disk.commit()

        if len(self.middleware.call_sync('disk.get_partitions_quick', disk, 10)) != len(parted_disk.partitions):
            # In some rare cases udev does not re-read the partition table correctly; force it
            self.middleware.call_sync('device.trigger_udev_events', f'/dev/{disk}')
            self.middleware.call_sync('device.settle_udev_events')
