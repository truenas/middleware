"""Detect the hardware this process is running on.

The entry point callers use to read the system: it reads DMI, asks ``detect``
which platform this is, and hands both to the pure ``classify`` half. ``detect``
reaches hardware as well -- it forks ``ipmi-raw``, queries udev and issues SES
ioctls -- so testing this path means mocking both.

Bhyve node detection goes through pyudev inside ``detect``, so udev has to be
running for a bhyve node to be recognized.

A detection failure propagates rather than degrading to a chassis-only answer: a
chassis tag cannot say whether a machine is one half of an HA pair, so answering
from it alone would invent an answer where none was obtained.
"""

from __future__ import annotations

from ixhardware import parse_dmi

from .classify import classify
from .detect import detect_platform
from .types import HardwareClass, HardwareInfo

__all__ = ("get_hardware_class", "get_hardware_info")


def get_hardware_info() -> HardwareInfo:
    """Return what this system is.

    Not cached: ``ixhardware.parse_dmi()`` and ``detect_platform()`` are each
    ``@cache``d and ``classify`` is pure.
    """
    dmi = parse_dmi()
    ha_platform: str = detect_platform()[0]
    return classify(dmi, ha_platform=ha_platform)


def get_hardware_class() -> HardwareClass:
    """Return the matrix column this system belongs to."""
    return get_hardware_info().hardware_class
