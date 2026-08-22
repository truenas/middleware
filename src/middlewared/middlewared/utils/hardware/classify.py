"""Pure classification of DMI into a platform and a hardware class.

Every input arrives as an argument, so this module performs no I/O and can be
exercised against synthesized ``DMIInfo`` without mocking. ``probe`` owns the
impure steps -- reading DMI and running ``detect``'s platform detection -- and
hands both results here as plain data.
"""

from __future__ import annotations

from collections.abc import Mapping

from ixhardware import TRUENAS_UNKNOWN, DMIInfo, get_chassis_hardware

from .types import HardwareClass, HardwareInfo, Platform

__all__ = ("classify", "classify_platform", "hardware_class_for")


def classify_platform(dmi: DMIInfo, *, ha_platform: str) -> Platform:
    """Classify `dmi` into a ``Platform``.

    `ha_platform` is the HARDWARE half of ``detect.detect_platform()``: the
    platform team's codename for this machine, or ``"MANUAL"``. It has no
    default -- defaulting it to ``"MANUAL"`` would silently demote every
    ``IXKVM`` and ``BHYVE`` caller to ``GENERIC``, which is an entitlement
    regression that raises nothing.

    Rules are applied in this order:

    1. `ha_platform` wins outright when it named something. ``IXKVM`` and
       ``BHYVE`` are the two HA virtual machine flavors; every other codename
       is iX-built appliance hardware. Codenames this does not recognize
       degrade to ``IX_HARDWARE`` rather than raising, so a platform shipped
       after this was written is still entitled as hardware.
    2. ``"MANUAL"`` is not an answer. It means only "not one half of an HA
       pair", which is true of R-series, Z-series, Minis and whiteboxes
       alike, so it falls through to the chassis tag: ``MINI`` when the tag
       names a Mini, ``IX_HARDWARE`` for any other recognized tag.
    3. Everything else is ``GENERIC``.

    Detection ahead of the chassis tag is a deliberate reversal of the
    ordering this used to apply. The consequence: a QEMU virtual machine
    stamped as an HA node is ``IXKVM`` even when its chassis tag claims to be
    a Mini, so it lands in the appliance column rather than the Mini one. The
    HA stamp is the more specific signal, and such a machine is standing in
    for an appliance whatever product name it advertises.
    """
    if ha_platform == "IXKVM":
        return Platform.IXKVM
    if ha_platform == "BHYVE":
        return Platform.BHYVE
    if ha_platform != "MANUAL":
        return Platform.IX_HARDWARE

    chassis: str = get_chassis_hardware(dmi)
    if chassis != TRUENAS_UNKNOWN:
        return Platform.MINI if "MINI" in chassis else Platform.IX_HARDWARE

    return Platform.GENERIC


_CLASS_BY_PLATFORM: Mapping[Platform, HardwareClass] = {
    Platform.IX_HARDWARE: HardwareClass.TRUENAS_HW,
    Platform.MINI: HardwareClass.MINI,
    # An HA virtual machine stands in for an appliance, so it is entitled as
    # one rather than as commodity hardware.
    Platform.IXKVM: HardwareClass.TRUENAS_HW,
    Platform.BHYVE: HardwareClass.TRUENAS_HW,
    Platform.GENERIC: HardwareClass.GENERIC,
}


def hardware_class_for(platform: Platform) -> HardwareClass:
    """Return the matrix column `platform` belongs to."""
    return _CLASS_BY_PLATFORM[platform]


def classify(dmi: DMIInfo, *, ha_platform: str) -> HardwareInfo:
    """Classify `dmi` into a full ``HardwareInfo``."""
    chassis: str = get_chassis_hardware(dmi)
    platform = classify_platform(dmi, ha_platform=ha_platform)
    return HardwareInfo(
        platform=platform,
        hardware_class=hardware_class_for(platform),
        chassis=chassis,
        ha_platform=ha_platform,
    )
