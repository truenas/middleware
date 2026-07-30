from __future__ import annotations

import enum
from dataclasses import dataclass

from ixhardware import TRUENAS_UNKNOWN

from middlewared.utils.license import LicenseInfo


class HardwareClass(enum.Enum):
    TRUENAS_HW = "TRUENAS_HW"
    MINI = "MINI"
    GENERIC = "GENERIC"

    @classmethod
    def from_chassis(cls, chassis: str) -> HardwareClass:
        if chassis == TRUENAS_UNKNOWN:
            return cls.GENERIC
        if "MINI" in chassis:
            return cls.MINI
        return cls.TRUENAS_HW


@dataclass(frozen=True, kw_only=True, slots=True)
class EntitlementFacts:
    hardware_class: HardwareClass
    """Hardware class this system belongs to."""
    license: LicenseInfo | None
    """Parsed license, or None when the system is unlicensed."""
