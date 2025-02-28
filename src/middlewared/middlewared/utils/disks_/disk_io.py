from os import lseek, write, SEEK_END, SEEK_SET
from struct import unpack
from uuid import UUID

from .gpt_parts import GptPartEntry, PART_TYPES

__all__ = ("read_gpt", "wipe_disk_quick")

_1MiB = 1048576


def wipe_disk_quick(dev_fd: int, disk_size: int | None = None) -> None:
    # Write first and last 32MiB of disk with zeros.
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
