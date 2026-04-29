import math
import pathlib
import subprocess

from middlewared.service import CallError, Service, private


def sgdisk_explicit_alignment(
    disk_size_bytes: int,
    sector_size_bytes: int,
    requested_partition_size: int,
) -> int | None:
    """
    Return the explicit GPT alignment that we need to pass to `sgdisk` in order to be able to create a partition
    of requested_partition_size bytes that fits on the disk.

    Assumptions:
    - Standard GPT layout
    - Protective MBR in sector 0
    - Primary GPT header in sector 1
    - Backup GPT header in last sector
    - Primary/backup partition-entry arrays on both ends
    - requested_partition_size must be a multiple of sector_size_bytes

    Returns:
    - alignment in sectors, or None if explicit alignment should not be specified
    """

    if disk_size_bytes % sector_size_bytes != 0:
        return None  # disk_size_bytes must be divisible by sector_size_bytes

    if sector_size_bytes % 512 != 0:
        return None  # sector_size_bytes must be divisible by 512

    if requested_partition_size % sector_size_bytes != 0:
        return None  # requested_partition_size must be divisible by sector_size_bytes

    total_sectors = disk_size_bytes // sector_size_bytes
    requested_partition_sectors = requested_partition_size // sector_size_bytes

    # GPT partition-entry array size in sectors
    mbr_size_bytes = 512
    gpt_header_size_bytes = 512
    num_partition_entries = 128
    partition_entry_size_bytes = 128
    entry_array_bytes = num_partition_entries * partition_entry_size_bytes
    gpt_size_bytes = mbr_size_bytes + gpt_header_size_bytes + entry_array_bytes
    gpt_size_sectors = math.ceil(gpt_size_bytes / sector_size_bytes)

    # Standard GPT usable range
    first_usable_sector = gpt_size_sectors
    last_usable_sector = total_sectors - gpt_size_sectors - 1

    latest_start_sector = last_usable_sector - requested_partition_sectors + 1
    if latest_start_sector < first_usable_sector:
        return None

    # Largest alignment A such that ceil(first_usable_sector / A) * A <= latest_start_sector
    best_alignment = None
    default_alignment = 1024 * 1024 // sector_size_bytes
    alignment = 1
    while alignment <= default_alignment:
        aligned_start = math.ceil(first_usable_sector / alignment) * alignment
        if aligned_start <= latest_start_sector:
            best_alignment = alignment

        alignment *= 2

    if best_alignment == default_alignment:
        return None

    return best_alignment * (sector_size_bytes // 512)


class DiskService(Service):

    @private
    def get_data_partition_size(self, disk, partition_start=0):
        size = self.middleware.call_sync("disk.get_dev_size", disk)
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
        sysfs = pathlib.Path(f"/sys/class/block/{disk}")
        if not sysfs.exists():
            raise CallError(f"Unable to retrieve disk details for {disk!r}")

        is_dif = next(sysfs.glob("device/scsi_disk/*/protection_type"), None)
        if is_dif is not None and is_dif.read_text().strip() != "0":
            # 0 == disabled, > 0 enabled
            raise CallError(f"Disk: {disk!r} is incorrectly formatted with Data Integrity Feature (DIF).")

        # wipe the disk (quickly) of any existing filesystems
        self.middleware.call_sync("disk.wipe", disk, "QUICK", False).wait_sync(raise_error=True)

        alignment = None
        if size is None:
            size = self.get_data_partition_size(disk)

        for info in self.middleware.call_sync("disk.get_disks", [disk]):
            # Old TrueNAS systems:
            # * Used the entire disk for the data partition
            # * Used smaller partition alignment
            #
            # When replacing a disk with such a partition, the new partition must be at least
            # as large as the one being replaced (ZFS requires this). However, when using a
            # larger alignment, the new partition may not fit on the disk. In that case,
            # we must use a smaller alignment.
            alignment = sgdisk_explicit_alignment(info.size_bytes, info.pbs, size)
            break

        cmd = ["sgdisk"]
        if alignment is not None:
            self.logger.info("Using non-default alignment %r for disk %r", alignment, disk)
            cmd += ["-a", str(alignment)]

        cmd += ["-n", f"1:0:+{int(size / 1024)}k", "-t", "1:BF01", f"/dev/{disk}"]

        try:
            subprocess.run(cmd, capture_output=True, check=True)
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

        if len(self.middleware.call_sync("disk.get_partitions_quick", disk, 10)) != 1:
            # In some rare cases udev does not re-read the partition table correctly; force it
            self.middleware.call_sync("device.trigger_udev_events", f"/dev/{disk}")
            self.middleware.call_sync("device.settle_udev_events")
