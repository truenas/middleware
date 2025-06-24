import os
import struct
import uuid
import zlib

from .gpt_parts import GptPartEntry, PART_TYPES

__all__ = ("read_gpt", "wipe_disk_quick", "create_gpt_partition")

_1MiB = 1048576
_2GiB = 2147483648
ZOL_PART_TYPE = "6a898cc3-1dd2-11b2-99a6-080020736631"


def wipe_disk_quick(dev_fd: int, disk_size: int | None = None) -> None:
    """Quickly wipe a disk by zeroing the first and last 32MB regions.

    This function performs a quick disk wipe by writing zeros to the beginning
    and end of the disk, which is sufficient to destroy most partition tables
    and filesystem signatures without wiping the entire disk.

    Args:
        dev_fd: File descriptor for the opened device
        disk_size: Size of the disk in bytes. If None, will be determined
                  automatically using lseek

    Returns:
        None

    Note:
        The device must be opened with write permissions before calling this function.
        This function writes 32MB of zeros at the beginning and 32MB at the end of the disk.
        This is much faster than a full wipe and sufficient for most use cases.
    """
    # Write first and last 32MiB of disk with zeros.
    if disk_size is None:
        disk_size = os.lseek(dev_fd, 0, os.SEEK_END)
        # seek back to the beginning of the disk
        os.lseek(dev_fd, 0, os.SEEK_SET)

    to_write = b"\x00" * _1MiB
    for i in range(32):
        # wipe first 32MB
        os.write(dev_fd, to_write)

    # seek to 32MiB before end of drive
    os.lseek(dev_fd, (disk_size - (_1MiB * 32)), os.SEEK_SET)
    for i in range(32):
        # wipe last 32MiB
        os.write(dev_fd, to_write)


def read_gpt(devobj: int | str, lbs: int) -> tuple[GptPartEntry]:
    """Read GPT partition entries from a device.

    Reads and parses the GPT (GUID Partition Table) from the specified device
    and returns a tuple of partition entries. This function can work with either
    a device path or an already opened file descriptor.

    Args:
        devobj: Device path (e.g., '/dev/sda') or file descriptor
        lbs: Logical block size in bytes (typically 512 or 4096)

    Returns:
        tuple[GptPartEntry]: Tuple of GPT partition entries found on the device.
                            Returns empty tuple if no valid GPT is found.

    Note:
        - Opens device in read-only mode to avoid triggering udev events
        - Only returns partitions that have a non-zero first_lba
        - Supports up to 128 partitions (GPT standard)
        - Automatically handles file descriptor lifecycle when given a device path
        - When given a file descriptor, assumes it's already positioned correctly
    """
    parts = list()
    should_close = False
    if isinstance(devobj, str):
        # it's _incredibly_ important to open this device
        # as read-only. Otherwise, udevd will trigger
        # events which will, ultimately, tear-down
        # by-partuuid symlinks (if the disk has relevant
        # partition information on it). Simply closing the
        # device after being opened in write mode causes
        # this behavior EVEN if the underlying device had
        # no changes to it. A miserable, undeterministic design.
        dev_fd = os.open(devobj, os.O_RDONLY)
        should_close = True
    else:
        dev_fd = devobj

    try:
        # GPT Header starts at LBA 1
        # For 4K native disks, we need to seek to LBA 1 * lbs
        os.lseek(dev_fd, lbs, os.SEEK_SET)
        gpt_header = os.read(dev_fd, max(512, lbs))[:512]  # GPT header is always 512 bytes
        if gpt_header[0:8] != b"EFI PART":
            # invalid gpt header so no reason to continue
            return tuple()

        partition_entry_lba = struct.unpack("<Q", gpt_header[72:80])[0]
        num_partitions = struct.unpack("<I", gpt_header[80:84])[0]
        partition_entry_size = struct.unpack("<I", gpt_header[84:88])[0]
        os.lseek(dev_fd, partition_entry_lba * lbs, os.SEEK_SET)
        for i in range(min(num_partitions, 128)):  # 128 is max gpt partitions
            entry = os.read(dev_fd, partition_entry_size)
            partition_type_guid = str(uuid.UUID(bytes_le=entry[0:16]))
            partition_type = PART_TYPES.get(partition_type_guid, "UNKNOWN")
            partition_unique_guid = str(uuid.UUID(bytes_le=entry[16:32]))
            first_lba = struct.unpack("<Q", entry[32:40])[0]
            last_lba = struct.unpack("<Q", entry[40:48])[0]

            try:
                name = entry[56:128].decode("utf-16").rstrip("\x00") or None
            except Exception:
                # very rare, but maybe scrambled data so we'll play it safe
                name = None

            if first_lba != 0:
                parts.append(
                    GptPartEntry(
                        partition_number=i + 1,
                        partition_type=partition_type,
                        partition_type_guid=partition_type_guid,
                        unique_partition_guid=partition_unique_guid,
                        partition_name=name,
                        first_lba=first_lba,
                        last_lba=last_lba,
                    )
                )
    finally:
        if should_close:
            os.close(dev_fd)

    return tuple(parts)


def create_gpt_partition(
    device: str | int,
    *,
    ts_512: int | None = None,
    lbs: int | None = None,
    pbs: int | None = None,
) -> uuid.UUID:
    """Create a GPT partition table with a single ZFS partition on the specified device.

    Creates a complete GPT (GUID Partition Table) structure on the specified device,
    including protective MBR, primary and secondary GPT headers, and partition entries.
    The partition is configured for ZFS use with proper alignment and sizing.

    Args:
        device: Path to the device (e.g., '/dev/sda' or 'sda') or file descriptor
        ts_512: Optional total number of 512-byte sectors. If None, reads from sysfs.
        lbs: Optional logical block size. If None, reads from sysfs.
        pbs: Optional physical block size. If None, reads from sysfs.

    Returns:
        uuid.UUID: The unique identifier (GUID) of the created partition

    Raises:
        ValueError: If there's insufficient space on the disk after applying
                   alignment constraints
        OSError: If the device cannot be opened or accessed

    Note:
        - The device must not be mounted or in use
        - Requires root privileges to access block devices
        - Creates a single partition spanning most of the disk with proper alignment
        - Reserves space at the end of the disk for resilience (up to 2GB or 1% of disk)
        - Uses 1MB alignment for optimal performance
        - For 4K native disks, uses sector 2048 as the first usable sector
    """
    if isinstance(device, str):
        dev_name = device.removeprefix("/dev/")
        dev_fd = os.open(f"/dev/{dev_name}", os.O_RDWR | os.O_EXCL)
        should_close = True
    else:
        dev_fd = device
        dev_name = os.path.basename(os.readlink(f"/proc/self/fd/{dev_fd}"))
        should_close = False

    try:
        if ts_512 is None:
            with open(f"/sys/block/{dev_name}/size") as f:
                ts_512 = int(f.read().strip())  # 512-byte sectors
        if lbs is None:
            with open(f"/sys/block/{dev_name}/queue/logical_block_size") as f:
                lbs = int(f.read().strip())
        if pbs is None:
            with open(f"/sys/block/{dev_name}/queue/physical_block_size") as f:
                pbs = int(f.read().strip())

        sector_ratio = lbs // 512
        ts = ts_512 // sector_ratio  # Total sectors in lbs units (4096-byte)
        alignment_in_sectors = _1MiB // lbs  # 1 MiB alignment in lbs units
        physical_alignment = pbs // lbs  # Should be 1 for 4K/4K disks
        min_start_lba = _align_sector(
            (34 * 512) // lbs, physical_alignment, "up"
        )  # Minimum GPT space
        first_usable = _align_sector(
            min_start_lba, alignment_in_sectors, "up"
        )  # Align to 1 MiB
        # For 4K native disks, set first_usable to 2048 in 4096-byte sectors
        if lbs == 4096:
            first_usable = 2048  # Directly set to 2048 (4096-byte sectors)

        one_percent_of_disk = int((lbs * ts) * 0.01)
        end_buffer_in_bytes = min(_2GiB, one_percent_of_disk)
        end_buffer_in_sectors = _align_sector(
            end_buffer_in_bytes // lbs, physical_alignment, "up"
        )
        secondary_gpt_sectors = (32 * 512) // lbs + 1  # 5 sectors for 4096-byte lbs
        max_end_lba = ts - end_buffer_in_sectors - secondary_gpt_sectors
        last_usable = _align_sector(max_end_lba, alignment_in_sectors, "down")

        if last_usable <= first_usable:
            raise ValueError(
                "Not enough space on disk after applying alignment constraints."
            )

        pmbr = _create_pmbr(ts, lbs)
        disk_guid = uuid.uuid4()
        partition_guid = uuid.uuid4()
        part_entries, part_entries_crc32 = _create_partition_entries(
            first_usable, last_usable, partition_guid, lbs, pbs
        )
        primary_gpt_header = _create_gpt_header(
            True, disk_guid, ts, part_entries_crc32, first_usable, last_usable, lbs, pbs
        )
        secondary_gpt_header = _create_gpt_header(
            False,
            disk_guid,
            ts,
            part_entries_crc32,
            first_usable,
            last_usable,
            lbs,
            pbs,
        )

        os.lseek(dev_fd, 0, os.SEEK_SET)
        os.write(dev_fd, pmbr)
        os.lseek(dev_fd, lbs, os.SEEK_SET)
        os.write(dev_fd, primary_gpt_header)
        os.lseek(dev_fd, 2 * lbs, os.SEEK_SET)
        os.write(dev_fd, part_entries)
        secondary_entries_lba = ts - secondary_gpt_sectors
        os.lseek(dev_fd, secondary_entries_lba * lbs, os.SEEK_SET)
        os.write(dev_fd, part_entries)
        os.lseek(dev_fd, (ts - 1) * lbs, os.SEEK_SET)
        os.write(dev_fd, secondary_gpt_header)
        return partition_guid
    finally:
        if should_close:
            os.close(dev_fd)


def _align_sector(sector: int, alignment: int, direction: str) -> int:
    """Align a sector number to the specified alignment boundary.

    This function aligns a sector number either up or down to the nearest
    boundary that is a multiple of the alignment value. This is essential
    for optimal disk performance and meeting hardware requirements.

    Args:
        sector: The sector number to align
        alignment: The alignment boundary (must be positive)
        direction: Direction to align - "up" rounds up to next boundary,
                  "down" rounds down to previous boundary

    Returns:
        int: The aligned sector number

    Raises:
        ValueError: If direction is not "up" or "down"
    """
    if direction == "up":
        return ((sector + alignment - 1) // alignment) * alignment
    elif direction == "down":
        return (sector // alignment) * alignment
    else:
        raise ValueError(f"Invalid direction: {direction!r}")


def _create_pmbr(ts: int, lbs: int) -> bytearray:
    """Create a Protective Master Boot Record (PMBR) for GPT.

    The PMBR is a legacy MBR that protects the GPT from tools that don't
    understand GPT partitioning. It contains a single partition entry of
    type 0xEE that spans the entire disk, preventing legacy tools from
    overwriting the GPT data.

    Args:
        ts: Total number of sectors on the disk (in logical block size units)
        lbs: Logical block size in bytes (typically 512 or 4096)

    Returns:
        bytearray: The complete PMBR sector data, padded to logical block size
    """
    pmbr = bytearray(lbs)
    pmbr[0:440] = bytearray(440)
    pmbr[440:444] = b"\x00\x00\x00\x00"  # Use fixed signature instead of random
    pmbr[444:446] = b"\x00\x00"
    partition_entry = bytearray(16)
    partition_entry[0] = 0x00
    partition_entry[1] = 0x00
    partition_entry[2] = 0x02
    partition_entry[3] = 0x00
    partition_entry[4] = 0xEE
    partition_entry[5] = 0xFF
    partition_entry[6] = 0xFF
    partition_entry[7] = 0xFF
    partition_entry[8:12] = struct.pack("<I", 1)
    size_in_lba = min(ts - 1, 0xFFFFFFFF)  # In lbs units (4096-byte sectors)
    partition_entry[12:16] = struct.pack("<I", size_in_lba)
    pmbr[446:462] = partition_entry
    pmbr[510:512] = b"\x55\xaa"
    return pmbr


def _create_partition_entries(
    first_usable: int, last_usable: int, partition_guid: uuid.UUID, lbs: int, pbs: int
) -> tuple[bytearray, int]:
    """Create the partition entries array for the GPT.

    Creates a 16KB partition entries array containing a single partition entry
    configured for ZFS use. The partition spans from first_usable to last_usable
    sectors and uses the ZFS partition type GUID.

    Args:
        first_usable: First usable sector for the partition (in logical block size units)
        last_usable: Last usable sector for the partition (in logical block size units)
        partition_guid: Unique identifier for this partition instance
        lbs: Logical block size in bytes (typically 512 or 4096)
        pbs: Physical block size in bytes (typically 512 or 4096)

    Returns:
        tuple[bytearray, int]: A tuple containing:
            - The complete partition entries array (16KB)
            - CRC32 checksum of the partition entries
    """
    num_partition_entries = 128
    partition_entry_size = 128
    total_size = num_partition_entries * partition_entry_size  # 16 KiB
    entries = bytearray(total_size)
    partition_type_guid = uuid.UUID(ZOL_PART_TYPE)
    entry = bytearray(partition_entry_size)
    entry[0:16] = partition_type_guid.bytes_le
    entry[16:32] = partition_guid.bytes_le
    entry[32:40] = struct.pack("<Q", first_usable)
    entry[40:48] = struct.pack("<Q", last_usable)
    entry[48:56] = struct.pack("<Q", 0)
    name = "data".encode("utf-16le")
    entry_start = 56
    entry_end = entry_start + len(name)
    entry[entry_start:entry_end] = name
    entries[0:partition_entry_size] = entry
    partition_entries_crc32 = zlib.crc32(entries) & 0xFFFFFFFF
    return entries, partition_entries_crc32


def _create_gpt_header(
    is_primary: bool,
    disk_guid: uuid.UUID,
    ts: int,
    partition_entries_crc32: int,
    first_usable: int,
    last_usable: int,
    lbs: int,
    pbs: int,
) -> bytearray:
    """Create a GPT header (primary or secondary).

    Creates a complete GPT header containing all necessary metadata for the
    partition table. GPT maintains two identical headers: primary at LBA 1
    and secondary at the last LBA, with each pointing to its corresponding
    partition entries array.

    Args:
        is_primary: True for primary header (LBA 1), False for secondary (last LBA)
        disk_guid: Unique identifier for this disk
        ts: Total number of sectors on the disk (in logical block size units)
        partition_entries_crc32: CRC32 checksum of the partition entries array
        first_usable: First usable sector for partitions
        last_usable: Last usable sector for partitions
        lbs: Logical block size in bytes (typically 512 or 4096)
        pbs: Physical block size in bytes (typically 512 or 4096)

    Returns:
        bytearray: The complete GPT header, padded to physical block size
    """
    header = bytearray(512)
    header[0:8] = b"EFI PART"
    header[8:12] = struct.pack("<I", 0x00010000)
    header[12:16] = struct.pack("<I", 92)
    header[16:20] = struct.pack("<I", 0)
    header[20:24] = struct.pack("<I", 0)
    header[24:32] = struct.pack("<Q", 1 if is_primary else ts - 1)
    header[32:40] = struct.pack("<Q", ts - 1 if is_primary else 1)
    header[40:48] = struct.pack("<Q", first_usable)
    header[48:56] = struct.pack("<Q", last_usable)
    header[56:72] = disk_guid.bytes_le
    secondary_entries_lba = ts - ((32 * 512) // lbs + 1)
    header[72:80] = struct.pack("<Q", 2 if is_primary else secondary_entries_lba)
    header[80:84] = struct.pack("<I", 128)
    header[84:88] = struct.pack("<I", 128)
    header[88:92] = struct.pack("<I", partition_entries_crc32)
    header[16:20] = struct.pack("<I", 0)
    header_crc32 = zlib.crc32(header[:92]) & 0xFFFFFFFF
    header[16:20] = struct.pack("<I", header_crc32)
    return header.ljust(pbs, b"\x00")
