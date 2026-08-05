"""Detect the hardware this process is running on.

The only module in this package that touches the system, and the only one that
needs mocking to test. It reads DMI, asks ``detect`` which platform this is,
and hands both to the pure ``classify`` half.

This module used to carry its own bhyve backplane scan, justified by reading
sysfs directly rather than going through udev: the two are equivalent, and
sysfs kept the module on the standard library and working even where udev is
not running. Delegating to ``detect`` reverses that rationale -- ``detect``
uses pyudev, so udev does now have to be running for a bhyve node to be
recognized. That is the accepted price of there being one copy of the
QEMU/bhyve rules instead of two that can drift apart.
"""

from __future__ import annotations

from functools import cache
import logging

from ixhardware import parse_dmi

from .classify import classify
from .detect import detect_platform
from .types import HardwareClass, HardwareInfo

__all__ = ("get_hardware_class", "get_hardware_info")

logger = logging.getLogger(__name__)


@cache
def get_hardware_info() -> HardwareInfo:
    """Return what this system is, computed once per process.

    ``ixhardware.parse_dmi()`` is itself cached, but detection forks
    ``ipmi-raw`` and issues SES ioctls, so the result is cached here as well.
    Nothing this reads can change without a reboot.
    """
    dmi = parse_dmi()
    try:
        # Only the HARDWARE half is wanted here. The NODE half answers "which
        # side of an HA pair am I", which is not a question this package asks.
        ha_platform: str = detect_platform()[0]
    except Exception:
        # Detection talks to enclosures and to the BMC, either of which can
        # fail on a machine that is misbehaving. "MANUAL" falls through to
        # chassis classification, which is exactly what this module did before
        # it consulted detection at all, so failing this way is no worse than
        # the behavior it replaced.
        logger.error("Platform detection failed; classifying from the chassis tag alone", exc_info=True)
        ha_platform = "MANUAL"

    return classify(dmi, ha_platform=ha_platform)


def get_hardware_class() -> HardwareClass:
    """Return the matrix column this system belongs to."""
    return get_hardware_info().hardware_class
