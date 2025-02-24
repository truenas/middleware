from dataclasses import dataclass
from fcntl import ioctl
from io import TextIOWrapper
from os import stat
from struct import unpack
from types import MappingProxyType
from typing import Literal
from uuid import UUID

# ioctl cmd for getting logical block size
BLKSSZGET = 0x1268
# there are a TON more but we only care about ZFS
PART_TYPES = MappingProxyType(
    {
        "21686148-6449-6e6f-744e-656564454649": "BIOS boot partition",  # boot drives
        "6a898cc3-1dd2-11b2-99a6-080020736631": "ZFS",  # linux
        "516e7cba-6ecf-11d6-8ff8-00022d09712b": "ZFS",  # freebsd
    }
)


@dataclass(slots=True, frozen=True, kw_only=True)
class SectorSizeInfo:
    logical_sector_size: int
    physical_sector_size: int


@dataclass(slots=True, frozen=True, kw_only=True)
class GptPartEntry:
    partition_number: int
    partition_type: Literal["ZFS", "UNKONWN"]
    partition_type_guid: str
    unique_partition_guid: str
    partition_name: str | None
    sector_info: SectorSizeInfo
    first_lba: int
    last_lba: int
    size_bytes: int


def __get_log_and_phys_blksz(f: TextIOWrapper) -> SectorSizeInfo:
    """Return a tuple of logical and physical sector size"""
    try:
        buf = bytearray(4)
        ioctl(f, BLKSSZGET, buf)
        return SectorSizeInfo(
            logical_sector_size=unpack("I", buf)[0],
            physical_sector_size=stat(f.fileno()).st_blksize,
        )
    except Exception:
        # fallback to 512 which is standard practice
        return SectorSizeInfo(
            logical_sector_size=512,
            physical_sector_size=512,
        )


def __get_part_type(guid: str) -> Literal["ZFS", "UNKNOWN"]:
    try:
        return PART_TYPES[guid]
    except KeyError:
        return "UNKNOWN"


def __get_gpt_parts_impl(device: str) -> tuple[GptPartEntry]:
    parts = list()
    with open(device, "rb") as f:
        # it's _incredibly_ important to open this device
        # as read-only. Otherwise, udevd will trigger
        # events which will, ultimately, tear-down
        # by-partuuid symlinks (if the disk has relevant
        # partition information on it). Simply closing the
        # device after being opened in write mode causes
        # this behavior EVEN if the underlying device had
        # no changes to it. A miserable, undeterministic design.
        ssi: SectorSizeInfo = __get_log_and_phys_blksz(f)

        # GPT Header starts at LBA 1
        gpt_header = f.read(1024)[512:]
        if gpt_header[0:8] != b"EFI PART":
            # invalid gpt header so no reason to continue
            return tuple()

        partition_entry_lba = unpack("<Q", gpt_header[72:80])[0]
        num_partitions = unpack("<I", gpt_header[80:84])[0]
        partition_entry_size = unpack("<I", gpt_header[84:88])[0]
        f.seek(partition_entry_lba * ssi.logical_sector_size)
        for i in range(min(num_partitions, 128)):  # 128 is max gpt partitions
            entry = f.read(partition_entry_size)
            partition_type_guid = str(UUID(bytes_le=entry[0:16]))
            partition_type = __get_part_type(partition_type_guid)
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
                        sector_info=ssi,
                        first_lba=first_lba,
                        last_lba=last_lba,
                        size_bytes=(last_lba - first_lba + 1) * ssi.logical_sector_size,
                    )
                )
    return tuple(parts)
