from dataclasses import dataclass
from struct import unpack, unpack_from
from uuid import UUID


@dataclass(slots=True, frozen=True, kw_only=True)
class PartitionEntry:
    number: int
    first_lba: int
    last_lba: int
    part_name: str
    disk_guid: str
    part_type_guid: str
    part_entry_guid: str


def read_gpt_partitions(device: str) -> list[PartitionEntry] | list:
    with open(f"/dev/{device.removeprefix('/dev/')}", "rb") as f:
        # it's _incredibly_ important to open this device
        # as read-only. Otherwise, udevd will trigger
        # events which will, ultimately, tear-down
        # by-partuuid symlinks (if the disk has relevant
        # partition information on it). Simply closing the
        # device after being opened in write mode causes
        # this behavior EVEN if the underlying device had
        # no changes to it. A miserable, undeterministic design.
        gpt_header = f.read(1024)[512:]  # GPT header starts at LBA 1
        if gpt_header[0:8] != b"EFI PART":
            return False

        # Unpack GPT header fields
        (
            _,  # signature unused
            _,  # revision unused
            _,  # header unused
            _,  # header_crc32 unused
            _,  # reserved unused
            _,  # current_lba unused
            _,  # backup_lba unused
            _,  # first_usable_lba unused
            _,  # last_usable_lba unused
            disk_guid_bytes,
            partition_entry_lba,
            num_part_entries,
            size_part_entry,
            _,  # partition_entry_array_crc32 unused
            _,  # unused
        ) = unpack("<8sIIIIQQQQ16sQIII420s", gpt_header)

        # Read partition entries
        f.seek(partition_entry_lba * 512)
        partitions = []
        for i in range(num_part_entries):
            entry = f.read(size_part_entry)
            if len(entry) < size_part_entry:
                # end of entries
                break

            part_name = entry[56:size_part_entry].decode("utf-16le", errors="ignore")
            partitions.append(
                PartitionEntry(
                    number=i + 1,
                    first_lba=unpack_from("<Q", entry, 32)[0],
                    last_lba=unpack_from("<Q", entry, 40)[0],
                    part_name=part_name.rstrip("\x00"),
                    disk_guid=str(UUID(bytes_le=disk_guid_bytes)),
                    part_type_guid=str(UUID(bytes_le=entry[0:16])),
                    part_entry_guid=str(UUID(bytes_le=entry[16:32])),
                )
            )
    return partitions
