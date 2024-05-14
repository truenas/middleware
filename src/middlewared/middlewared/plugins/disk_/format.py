import pathlib

import parted

from middlewared.service import CallError, private, Service


class DiskService(Service):

    @private
    def format(self, disk, swap_size_gb=None):
        """Format a data drive with a maximized data partition"""
        sysfs = pathlib.Path(f'/sys/class/block/{disk}')
        if not sysfs.exists():
            raise CallError(f'Unable to retrieve disk details for {disk!r}')

        is_dif = next(sysfs.glob('device/scsi_disk/*/protection_type'), None)
        if is_dif is not None and is_dif.read_text().strip() != '0':
            # 0 == disabled, > 0 enabled
            raise CallError(f'Disk: {disk!r} is incorrectly formatted with Data Integrity Feature (DIF).')

        dev = parted.getDevice(f'/dev/{disk}')
        for i in range(2):
            if not dev.clobber():
                # clobber() wipes partition label info from disk but during testing
                # on an m40 HA system, the disk had to be clobber()'ed twice before
                # fdisk -l wouldn't show any partitions. Only doing it once showed
                # the following output
                # Disk /dev/sda: 10.91 TiB, 12000138625024 bytes, 2929721344 sectors
                # Disk model: HUH721212AL4200
                # Units: sectors of 1 * 4096 = 4096 bytes
                # Sector size (logical/physical): 4096 bytes / 4096 bytes
                # I/O size (minimum/optimal): 4096 bytes / 4096 bytes
                # Disklabel type: dos
                # Disk identifier: 0x00000000
                #
                # Device     Boot Start        End    Sectors  Size Id Type
                # /dev/sda1           1 2929721343 2929721343 10.9T ee GPT
                raise CallError(f'Failed on attempt #{i} clearing partition labels for {disk!r}')

        parted_disk = parted.freshDisk(dev, 'gpt')
        regions = sorted(parted_disk.getFreeSpaceRegions(), key=lambda x: x.length)[-1]
        geom = parted.Geometry(start=regions.start, end=regions.end, device=dev)
        fs = parted.FileSystem(type='zfs', geometry=geom)
        part = parted.Partition(disk=parted_disk, type=parted.PARTITION_NORMAL, fs=fs, geometry=geom)
        part.name = 'data'  # give a human readable name to the label
        parted_disk.addPartition(part, constraint=dev.optimalAlignedConstraint)
        parted_disk.commit()
        if len(self.middleware.call_sync('disk.get_partitions_quick', disk)) != len(parted_disk.partitions):
            # In some rare cases udev does not re-read the partition table correctly; force it
            self.middleware.call_sync('device.trigger_udev_events', f'/dev/{disk}')
            self.middleware.call_sync('device.settle_udev_events')
