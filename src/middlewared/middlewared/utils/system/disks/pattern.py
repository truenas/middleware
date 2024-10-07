from dataclasses import dataclass
from re import compile as re_compile, Pattern

__all__ = ("REPATTERNS",)


@dataclass(slots=True, frozen=True)
class REPatterns:
    SD: Pattern = re_compile(r"^sd[a-z]+$")
    """sda but not sda1 etc"""
    NVME: Pattern = re_compile(r"^nvme\d+n\d+$")
    """nvme0n1 but not nvme0n1p1 etc"""
    PMEM: Pattern = re_compile(r"^pmem\d+$")
    """pmem0 but not pmem0p1 etc"""

    def is_valid(self, value: str) -> bool:
        if self.SD.match(value):
            return True
        elif self.NVME.match(value):
            return True
        elif self.PMEM.match(value):
            return True
        return False


REPATTERNS = REPatterns()
