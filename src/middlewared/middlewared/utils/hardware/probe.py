"""Detect the hardware this process is running on.

The only module in this package that touches the system, and the only one that
needs mocking to test. It reads DMI, asks ``detect`` which platform this is,
and hands both to the pure ``classify`` half.

This module used to carry its own bhyve backplane scan, justified by reading
sysfs directly rather than going through udev: the two are equivalent, and
sysfs kept the module on the standard library and working even where udev is
not running. Delegating to ``detect`` reverses that rationale -- ``detect``
uses pyudev, so udev does now have to be running for a bhyve node to be
recognized. A detection failure propagates out of this module rather than
degrading to a chassis-only classification: a chassis tag cannot say whether a
machine is one half of an HA pair, so answering from it alone would be
inventing an answer where none was obtained.
"""

from __future__ import annotations

from functools import cache

from ixhardware import parse_dmi

from .classify import classify
from .detect import detect_platform
from .types import HardwareClass, HardwareInfo

__all__ = ("get_hardware_class", "get_hardware_info")


@cache
def get_hardware_info() -> HardwareInfo:
    """Return what this system is, computed once per process.

    ``ixhardware.parse_dmi()`` is itself cached, but detection forks
    ``ipmi-raw`` and issues SES ioctls, so the result is cached here as well.
    Nothing this reads can change without a reboot.
    """
    dmi = parse_dmi()
    # Only the HARDWARE half is wanted here. The NODE half answers "which
    # side of an HA pair am I", which is not a question this package asks.
    ha_platform: str = detect_platform()[0]
    return classify(dmi, ha_platform=ha_platform)


def get_hardware_class() -> HardwareClass:
    """Return the matrix column this system belongs to."""
    return get_hardware_info().hardware_class
