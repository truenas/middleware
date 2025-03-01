from os import lseek, urandom, write, SEEK_END, SEEK_SET
from struct import pack, unpack
from typing import Literal
from uuid import uuid4, UUID
from zlib import crc32

from .gpt_parts import GptPartEntry, PART_TYPES, ZOL_PART_TYPE

__all__ = ("read_gpt", "wipe_disk_quick")

_1MiB = 1048576
_2GiB = 2147483648


def wipe_disk_quick(dev_fd: int, disk_size: int | None = None) -> None:
    # Write first and last 32MiB of disk with zer
    if disk_size is None:
        disk_size = lseek(dev_fd, 0, SEEK_END)
        # seek back to the beginning of the disk
        lseek(dev_fd, 0, SEEK_SET)

    to_write = b"0" * _1MiB
    for i in range(32):
        # wipe first 32MB
        write(dev_fd, to_write)

    # seek to 32MiB before end of drive
    lseek(dev_fd, (disk_size - (_1MiB * 32)), SEEK_SET)
    for i in range(32):
        # wipe last 32MiB
        write(dev_fd, to_write)


def read_gpt(devobj: int | str, lbs: int) -> tuple[GptPartEntry]:
    parts = list()
    with open(devobj, "rb") as f:
        # it's _incredibly_ important to open this device
        # as read-only. Otherwise, udevd will trigger
        # events which will, ultimately, tear-down
        # by-partuuid symlinks (if the disk has relevant
        # partition information on it). Simply closing the
        # device after being opened in write mode causes
        # this behavior EVEN if the underlying device had
        # no changes to it. A miserable, undeterministic design.

        # GPT Header starts at LBA 1
        gpt_header = f.read(1024)[512:]
        if gpt_header[0:8] != b"EFI PART":
            # invalid gpt header so no reason to continue
            return tuple()

        partition_entry_lba = unpack("<Q", gpt_header[72:80])[0]
        num_partitions = unpack("<I", gpt_header[80:84])[0]
        partition_entry_size = unpack("<I", gpt_header[84:88])[0]
        f.seek(partition_entry_lba * lbs)
        for i in range(min(num_partitions, 128)):  # 128 is max gpt partitions
            entry = f.read(partition_entry_size)
            partition_type_guid = str(UUID(bytes_le=entry[0:16]))
            partition_type = PART_TYPES.get(partition_type_guid, "UNKNOWN")
            partition_unique_guid = str(UUID(bytes_le=entry[16:32]))
            first_lba = unpack("<Q", entry[32:40])[0]
            last_lba = unpack("<Q", entry[40:48])[0]

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
    return tuple(parts)


######### write gpt functions #########
def write_gpt(dev_fd: int, lbs: int, ts: int) -> UUID:
    """
    Args:
        dev_fd: open file descriptor of the disk
        lbs: logcal block size
        ts: total sectors of disk
    """
    # Alignment size in sectors (1 MiB alignment)
    alignment_in_sectors = _1MiB // lbs
    # Minimum starting LBA (must be at least 34 to allow space for GPT structures)
    min_start_lba = 34
    # First usable LBA aligned to 1 MiB boundary
    first_usable = max(
        align_sector(
            min_start_lba,
            alignment_in_sectors,
            "up",
        ),
        alignment_in_sectors,
    )
    # Maximum ending LBA. We ensure at least 2 GiB space at the end of disk OR
    # a maximum of 1% of the total size of the disk. This is to allow someone
    # to replace an existing disk with one that is nominal in size
    one_percent_of_disk = int((lbs * ts) * 0.01)
    end_buffer_in_bytes = min(_2GiB, one_percent_of_disk)
    end_buffer_in_sectors = end_buffer_in_bytes // lbs
    max_end_lba = ts - end_buffer_in_sectors - 1
    # Last usable LBA aligned to 1 MiB boundary
    last_usable = align_sector(max_end_lba, alignment_in_sectors, "down")

    # Ensure that last_usable is greater than first_usable
    if last_usable <= first_usable:
        raise ValueError(
            "Not enough space on disk after applying alignment constraints."
        )

    pmbr = create_pmbr(ts)
    disk_guid = uuid4()
    partition_guid = uuid4()
    part_entries, part_entries_crc32 = create_partition_entries(
        first_usable, last_usable, partition_guid
    )
    primary_gpt_header = create_gpt_header(
        True,
        disk_guid,
        ts,
        part_entries_crc32,
        first_usable,
        last_usable,
        lbs,
    )
    secondary_gpt_header = create_gpt_header(
        False,
        disk_guid,
        ts,
        part_entries_crc32,
        first_usable,
        last_usable,
        lbs,
    )
    # PMBR
    lseek(dev_fd, 0, SEEK_SET)
    write(dev_fd, pmbr)
    # Write primary GPT header at LBA 1
    lseek(dev_fd, lbs, SEEK_SET)
    write(dev_fd, primary_gpt_header)
    # Write partition entries starting at LBA 2
    lseek(dev_fd, 2 * lbs, SEEK_SET)
    write(dev_fd, part_entries)
    # Write secondary partition entries at LBA total sectors - 33
    lseek(dev_fd, (ts - 33) * lbs, SEEK_SET)
    write(dev_fd, part_entries)
    # Write secondary GPT header at last LBA
    lseek(dev_fd, (ts - 1) * lbs, SEEK_SET)
    write(dev_fd, secondary_gpt_header)
    return partition_guid


def align_sector(sector: int, alignment: int, direction: Literal["up", "down"]) -> int:
    if direction == "up":
        return ((sector + alignment - 1) // alignment) * alignment
    elif direction == "down":
        return (sector // alignment) * alignment
    else:
        raise ValueError(f"Invalid direction: {direction!r}")


def create_pmbr(ts: int) -> bytearray:
    pmbr = bytearray(512)
    pmbr[0:440] = bytearray(440)  # Boot code area, zero-filled
    pmbr[440:444] = urandom(4)  # Disk signature, random
    pmbr[444:446] = b"\x00\x00"  # Usually zeros

    # Partition entry starts at offset 446
    partition_entry = bytearray(16)
    partition_entry[0] = 0x00  # Boot indicator
    partition_entry[1] = 0x00  # Starting head
    partition_entry[2] = 0x02  # Starting sector
    partition_entry[3] = 0x00  # Starting cylinder
    partition_entry[4] = 0xEE  # Partition type (protective MBR)
    partition_entry[5] = 0xFF  # Ending head
    partition_entry[6] = 0xFF  # Ending sector
    partition_entry[7] = 0xFF  # Ending cylinder
    partition_entry[8:12] = pack("<I", 1)  # Starting LBA (sector 1)
    if ts < 0xFFFFFFFF:
        size_in_lba = ts - 1
    else:
        size_in_lba = 0xFFFFFFFF
    partition_entry[12:16] = pack("<I", size_in_lba)
    pmbr[446:462] = partition_entry
    pmbr[510:512] = b"\x55\xaa"  # Boot signature
    return pmbr


def create_partition_entries(
    first_usable: int, last_usable: int, partition_guid: UUID
) -> tuple[bytearray, int]:
    num_partition_entries = 128
    partition_entry_size = 128
    entries = bytearray(num_partition_entries * partition_entry_size)
    partition_type_guid = UUID(ZOL_PART_TYPE)
    entry = bytearray(partition_entry_size)
    entry[0:16] = partition_type_guid.bytes_le
    entry[16:32] = partition_guid.bytes_le
    entry[32:40] = pack("<Q", first_usable)
    entry[40:48] = pack("<Q", last_usable)
    entry[48:56] = pack("<Q", 0)  # Attributes
    # TODO: just "data"? we could be a bit more clever...
    name = "data".encode("utf-16le")
    len_name = 56 + len(name)
    entry[56:len_name] = name
    entries[0:partition_entry_size] = entry

    # Compute CRC32 of partition entries
    partition_entries_crc32 = crc32(entries) & 0xFFFFFFFF
    return entries, partition_entries_crc32


def create_gpt_header(
    is_primary: bool,
    disk_guid: UUID,
    ts: int,
    partition_entries_crc32: int,
    first_usable: int,
    last_usable: int,
    lbs: int,
) -> bytearray:
    header = bytearray(92)
    header[0:8] = b"EFI PART"  # Signature
    header[8:12] = pack("<I", 0x00010000)  # Revision
    header[12:16] = pack("<I", 92)  # Header size
    header[16:20] = pack("<I", 0)  # CRC32 of header (calculated later)
    header[20:24] = pack("<I", 0)  # Reserved
    header[24:32] = pack("<Q", 1 if is_primary else ts - 1)  # Current LBA
    header[32:40] = pack("<Q", ts - 1 if is_primary else 1)  # Backup LBA
    header[40:48] = pack("<Q", first_usable)  # First usable LBA
    header[48:56] = pack("<Q", last_usable)  # Last usable LBA
    header[56:72] = disk_guid.bytes_le  # Disk GUID
    header[72:80] = pack(
        "<Q", 2 if is_primary else ts - 33
    )  # Starting LBA of partition entries array
    header[80:84] = pack("<I", 128)  # Number of partition entries
    header[84:88] = pack("<I", 128)  # Size of each partition entry
    header[88:92] = pack("<I", partition_entries_crc32)  # CRC32 of parts entries array
    header[16:20] = pack("<I", 0)  # Set CRC32 field to zero before calculating
    header_crc32 = crc32(header) & 0xFFFFFFFF  # Compute header CRC32
    header[16:20] = pack("<I", header_crc32)
    padded_header = header.ljust(lbs, b"\x00")  # Pad to sector size
    return padded_header
