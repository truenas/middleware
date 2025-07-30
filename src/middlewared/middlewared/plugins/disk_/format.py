import pathlib
import subprocess

from middlewared.service import CallError, private, Service


class DiskService(Service):

    @private
    def get_data_partition_size(self, disk, partition_start=0):
        size = self.middleware.call_sync('disk.get_dev_size', disk)
        # Reserve 2 GiB or disk space (but no more than 1%) to allow this disk to be replaced with a slightly
        # smaller one in the future.
        size = size - int(min(2 * 1024 ** 3, size * 0.01))
        # Subtract any preceding partition sizes
        size -= partition_start
        # Align the partition size to the even number of MiB
        align = 1024 ** 2
        size = size // align * align
        return size

    @private
    def format(self, disk, size=None):
        """Format a data drive"""
        sysfs = pathlib.Path(f'/sys/class/block/{disk}')
        if not sysfs.exists():
            raise CallError(f'Unable to retrieve disk details for {disk!r}')

        is_dif = next(sysfs.glob('device/scsi_disk/*/protection_type'), None)
        if is_dif is not None and is_dif.read_text().strip() != '0':
            # 0 == disabled, > 0 enabled
            raise CallError(f'Disk: {disk!r} is incorrectly formatted with Data Integrity Feature (DIF).')

        # wipe the disk (quickly) of any existing filesystems
        self.middleware.call_sync('disk.wipe', disk, 'QUICK', False).wait_sync(raise_error=True)

        if size is None:
            size = self.get_data_partition_size(disk)

        try:
            subprocess.run(["sgdisk", "-n", f"1:0:+{int(size / 1024)}k", "-t", "1:BF01", f"/dev/{disk}"],
                           capture_output=True,
                           check=True)
        except subprocess.CalledProcessError as e:
            error = e.stderr.decode("utf-8", "ignore").strip()
            if "Could not create partition" in error:
                error = (
                    f"Could not create a partition of {size} bytes on disk {disk} because the disk is too small. "
                    "If you are replacing a disk in a pool, please ensure that the new disk is not smaller than "
                    "the disk being replaced.\n\n"
                    f"{error}"
                )
            else:
                error = f"Failed formatting disk {disk!r}: {error}"

            raise CallError(error)

        if len(self.middleware.call_sync('disk.get_partitions_quick', disk, 10)) != 1:
            # In some rare cases udev does not re-read the partition table correctly; force it
            self.middleware.call_sync('device.trigger_udev_events', f'/dev/{disk}')
            self.middleware.call_sync('device.settle_udev_events')
