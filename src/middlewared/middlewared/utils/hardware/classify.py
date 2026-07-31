"""Pure classification of DMI into a platform and a hardware class.

Every input arrives as an argument, so this module performs no I/O and can be
exercised against synthesized ``DMIInfo`` without mocking. ``probe`` owns the
one impure step -- reading DMI and the bhyve backplane -- and hands the result
here.
"""

from __future__ import annotations

from collections.abc import Mapping

from ixhardware import TRUENAS_UNKNOWN, DMIInfo, get_chassis_hardware

from .types import HardwareClass, HardwareInfo, Platform

__all__ = ("classify", "classify_platform", "hardware_class_for")


def classify_platform(dmi: DMIInfo, *, ha_backplane_present: bool = False) -> Platform:
    """Classify `dmi` into a ``Platform``.

    Rules are applied in this order:

    1. A recognized chassis tag wins outright: ``MINI`` when the tag names a
       Mini, ``IX_HARDWARE`` otherwise.
    2. QEMU whose system serial is stamped as an HA node (``ha`` prefix, or a
       ``_c1``/``_c2`` suffix) is ``IXKVM``.
    3. A bhyve guest is ``BHYVE`` only when the HA backplane was found; the
       caller supplies that as `ha_backplane_present` because probing for it
       is I/O.
    4. Everything else is ``GENERIC``.

    The chassis-first ordering deliberately differs from ``detect_platform``,
    which tests for QEMU before it looks at the product name. The consequence
    is intended: a QEMU virtual machine spoofing a ``TRUENAS-*`` product name
    classifies as hardware here, because what this answers is "which column of
    the feature matrix", and a machine claiming to be an appliance is taken at
    its word. ``detect_platform`` is answering a different question -- which
    HA node am I -- where the QEMU stamp is the more specific signal.
    """
    chassis: str = get_chassis_hardware(dmi)
    if chassis != TRUENAS_UNKNOWN:
        return Platform.MINI if "MINI" in chassis else Platform.IX_HARDWARE

    if dmi.system_manufacturer == "QEMU":
        serial: str = dmi.system_serial_number
        if serial.startswith("ha") or serial.endswith(("_c1", "_c2")):
            return Platform.IXKVM

    if dmi.system_product_name == "BHYVE" and ha_backplane_present:
        return Platform.BHYVE

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


def classify(dmi: DMIInfo, *, ha_backplane_present: bool = False) -> HardwareInfo:
    """Classify `dmi` into a full ``HardwareInfo``."""
    chassis: str = get_chassis_hardware(dmi)
    platform = classify_platform(dmi, ha_backplane_present=ha_backplane_present)
    return HardwareInfo(
        platform=platform,
        hardware_class=hardware_class_for(platform),
        chassis=chassis,
    )
