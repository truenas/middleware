from __future__ import annotations

from dataclasses import dataclass

from middlewared.utils.hardware import HardwareClass
from middlewared.utils.license import LicenseInfo

# HardwareClass is re-exported: it is half of AlertFacts, so everything building
# facts wants both names, and only this package's own layering cares that it is
# defined elsewhere.
__all__ = ("AlertFacts", "HardwareClass")


@dataclass(frozen=True, kw_only=True, slots=True)
class AlertFacts:
    """The only facts an alert applicability decision may rest on."""

    hardware_class: HardwareClass
    """Which hardware class this system belongs to."""
    license: LicenseInfo | None
    """Parsed license, or None when the system is unlicensed."""
