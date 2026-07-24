from __future__ import annotations

import enum
import typing
from dataclasses import dataclass

from ixhardware import TRUENAS_UNKNOWN

if typing.TYPE_CHECKING:
    from middlewared.plugins.truenas.license_utils import LicenseInfo


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
    is_ha_capable: bool
    """Whether the platform is HA capable (failover.hardware != MANUAL)."""
    license: LicenseInfo | None
    """Parsed license, or None when the system is unlicensed."""
