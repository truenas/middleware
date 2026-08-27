from __future__ import annotations

from dataclasses import dataclass

from middlewared.utils.hardware import HardwareClass
from middlewared.utils.license import LicenseInfo

__all__ = ("EntitlementFacts", "HardwareClass")


@dataclass(frozen=True, kw_only=True, slots=True)
class EntitlementFacts:
    hardware_class: HardwareClass
    """Hardware class this system belongs to."""
    license: LicenseInfo | None
    """Parsed license, or None when the system is unlicensed."""
