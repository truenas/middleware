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
    platform team's codename for this machine, or ``"MANUAL"``.

    Rules are applied in this order:

    1. `ha_platform` wins outright when it named something. ``IXKVM`` and
       ``BHYVE`` are virtual; every other codename is iX-built appliance
       hardware. An unrecognized codename degrades to ``IX_HARDWARE`` rather
       than raising, so a newly shipped platform is still entitled as hardware.
    2. ``"MANUAL"`` is not an answer. It means only "not one half of an HA
       pair", which is true of R-series, Z-series, Minis and whiteboxes
       alike, so it falls through to the chassis tag: ``MINI`` when the tag
       names a Mini, ``IX_HARDWARE`` for any other recognized tag.
    3. Everything else is ``GENERIC``.

    Detection runs ahead of the chassis tag, so a QEMU virtual machine stamped
    as an HA node is ``IXKVM`` even when its chassis tag names a Mini: the HA
    stamp is the more specific signal.
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
    return _CLASS_BY_PLATFORM[platform]


def classify(dmi: DMIInfo, *, ha_platform: str) -> HardwareInfo:
    chassis: str = get_chassis_hardware(dmi)
    platform = classify_platform(dmi, ha_platform=ha_platform)
    return HardwareInfo(
        platform=platform,
        hardware_class=hardware_class_for(platform),
        chassis=chassis,
        ha_platform=ha_platform,
    )
