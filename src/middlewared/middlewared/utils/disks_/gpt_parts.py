from dataclasses import dataclass
from types import MappingProxyType

__all__ = ("PART_TYPES", "GptPartEntry")

# there are a TON more but we only care about a few
PART_TYPES = MappingProxyType(
    {
        "21686148-6449-6e6f-744e-656564454649": "BIOS Boot Partition",  # boot drives
        "c12a7328-f81f-11d2-ba4b-00a0c93ec93b": "EFI System Partition",  # boot drives
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
    disk_name: str  # Parent disk name (e.g., 'sda')
    lbs: int  # Logical block size in bytes

    @property
    def name(self) -> str:
        """Partition device name (e.g., 'sda1')"""
        return f"{self.disk_name}{self.partition_number}"

    @property
    def disk(self) -> str:
        """Parent disk name"""
        return self.disk_name

    @property
    def partition_uuid(self) -> str:
        """Alias for unique_partition_guid for compatibility"""
        return self.unique_partition_guid

    @property
    def start_sector(self) -> int:
        """Starting sector (same as first_lba for GPT)"""
        return self.first_lba

    @property
    def end_sector(self) -> int:
        """Ending sector (same as last_lba for GPT)"""
        return self.last_lba

    @property
    def start_byte(self) -> int:
        """Start position in bytes"""
        return self.first_lba * self.lbs

    @property
    def end_byte(self) -> int:
        """End position in bytes (inclusive)"""
        return ((self.last_lba + 1) * self.lbs) - 1

    @property
    def size_bytes(self) -> int:
        """Total size in bytes"""
        return (self.last_lba - self.first_lba + 1) * self.lbs

    def to_dict(self) -> dict:
        """Return all fields and computed properties as a dictionary"""
        return {
            'name': self.name,
            'disk': self.disk,
            'partition_type': self.partition_type,
            'partition_type_guid': self.partition_type_guid,
            'partition_number': self.partition_number,
            'partition_uuid': self.partition_uuid,
            'partition_name': self.partition_name,
            'start_sector': self.start_sector,
            'end_sector': self.end_sector,
            'start_byte': self.start_byte,
            'end_byte': self.end_byte,
            'size_bytes': self.size_bytes,
        }
