"""Hardware vocabulary.

Definitions only: the enums and the record every other module in this package
speaks in. No detection, no policy, no I/O -- the sole piece of logic here is
``HardwareClass.from_chassis``, which is a pure string classification kept
beside the enum it produces.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from ixhardware import TRUENAS_UNKNOWN

__all__ = ("HardwareClass", "HardwareInfo", "Platform")


class Platform(enum.Enum):
    """What kind of machine this is, at the granularity detection can resolve.

    Finer-grained than ``HardwareClass``: it separates the two HA virtual
    machine flavors from each other and from real iX hardware, which matters
    for detection even where it does not change the entitlement answer.
    """

    IX_HARDWARE = "IX_HARDWARE"
    """iX-built appliance other than a Mini, identified by its chassis tag."""
    MINI = "MINI"
    """iX Mini appliance."""
    IXKVM = "IXKVM"
    """QEMU/KVM virtual machine provisioned as an HA node."""
    BHYVE = "BHYVE"
    """bhyve virtual machine provisioned as an HA node."""
    GENERIC = "GENERIC"
    """Anything else: commodity hardware or an ordinary virtual machine."""


class HardwareClass(enum.Enum):
    """The hardware axis of the product feature matrix.

    Coarser than ``Platform``: entitlement policy only ever needs to know
    which of these three columns a system sits in.
    """

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
class HardwareInfo:
    """Everything detection concluded about this machine."""

    platform: Platform
    """Platform this system was classified as."""
    hardware_class: HardwareClass
    """Matrix column that platform maps to."""
    chassis: str
    """Raw chassis tag, or ``TRUENAS_UNKNOWN`` when the system is not iX-built."""
