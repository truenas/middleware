from dataclasses import dataclass
from types import MappingProxyType

__all__ = ("PART_TYPES", "GptPartEntry")

# there are a TON more but we only care about a few
PART_TYPES = MappingProxyType(
    {
        "21686148-6449-6e6f-744e-656564454649": "BIOS Boot Partition",  # boot drives
        "c12a7328-f81f-11d2-ba4b-00a0c93ec93b": "EFI System Parition",  # boot drives
        "6a898cc3-1dd2-11b2-99a6-080020736631": "ZFS",  # linux
        "516e7cba-6ecf-11d6-8ff8-00022d09712b": "ZFS",  # freebsd
    }
)


@dataclass(slots=True, frozen=True, kw_only=True)
class GptPartEntry:
    partition_number: int
    partition_type: str
    partition_type_guid: str
    unique_partition_guid: str
    partition_name: str | None
    first_lba: int
    last_lba: int
