"""Hardware vocabulary.

The enums and the record every other module in this package speaks in.
Definitions only: no detection, no policy, no I/O.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

__all__ = ("HardwareClass", "HardwareInfo", "Platform")


class Platform(enum.Enum):
    """What kind of machine this is, at the granularity detection can resolve.

    Finer-grained than ``HardwareClass``: it separates the HA virtual machine
    flavors from each other and from real iX hardware, which matters for
    detection even where it does not change the entitlement answer.
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

    @property
    def is_appliance(self) -> bool:
        """Whether this is iX-built appliance hardware.

        A Mini is iX-built but is not this: it sits in its own matrix column, and every
        gate that says "appliance" means the column a Mini is not in.
        """
        return self is HardwareClass.TRUENAS_HW


@dataclass(frozen=True, kw_only=True, slots=True)
class HardwareInfo:
    """Everything detection concluded about this machine."""

    platform: Platform
    hardware_class: HardwareClass
    chassis: str
    """Raw chassis tag, or ``TRUENAS_UNKNOWN`` when the system is not iX-built."""
    ha_platform: str
    """HARDWARE half of ``detect.detect_platform()``: the platform team's
    codename for this machine, or ``"MANUAL"``.

    It has no default on purpose. A default would have to be ``"MANUAL"``,
    which is the not-HA-capable answer, and every construction site that
    forgot to supply the real value would silently receive it with nothing
    raising to say so.
    """

    @property
    def is_ha_capable(self) -> bool:
        """Whether this machine is one half of an HA pair.

        Deliberately not ``hardware_class.is_appliance``, which is true of
        single-controller appliances too. ``"MANUAL"`` is what says this
        machine is not one half of an HA pair.
        """
        return self.ha_platform != "MANUAL"
