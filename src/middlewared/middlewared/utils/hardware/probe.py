"""Detect the hardware this process is running on.

The only module in this package that touches the system, and the only one that
needs mocking to test. It reads DMI, probes for the bhyve HA backplane when DMI
says the guest is bhyve, and hands both to the pure ``classify`` half.

The backplane probe reads sysfs directly rather than going through udev. The
two are equivalent: ``udev_device_get_sysattr_value(dev, "device/model")``
reads ``<syspath>/device/model``, and ``/sys/class/scsi_generic/<name>`` is a
symlink to that syspath, so both resolve to the same file. Reading sysfs keeps
this module on the standard library and works even where udev is not running.
"""

from __future__ import annotations

from functools import cache
import glob

from ixhardware import parse_dmi

from .classify import classify
from .types import HardwareClass, HardwareInfo

__all__ = ("get_hardware_class", "get_hardware_info")

_SCSI_GENERIC_MODEL_GLOB = "/sys/class/scsi_generic/*/device/model"
_HA_BHYVE_MODELS = frozenset({"TrueNAS_A", "TrueNAS_B"})


def _bhyve_ha_backplane_present() -> bool:
    """True when a bhyve HA backplane device is attached.

    The bhyve host exposes a scsi_generic device whose inquiry model names the
    node position. Its presence is what distinguishes an HA bhyve guest from an
    ordinary one. A device that cannot be read is skipped rather than fatal --
    sysfs entries come and go, and one unreadable entry says nothing about the
    others.
    """
    for path in glob.glob(_SCSI_GENERIC_MODEL_GLOB):
        try:
            with open(path) as f:
                model = f.read().strip()
        except OSError:
            continue
        if model in _HA_BHYVE_MODELS:
            return True

    return False


@cache
def get_hardware_info() -> HardwareInfo:
    """Return what this system is, computed once per process.

    ``ixhardware.parse_dmi()`` is itself cached, but the backplane probe is
    not, so the result is cached here as well. Nothing this reads can change
    without a reboot.
    """
    dmi = parse_dmi()
    is_bhyve: bool = dmi.system_product_name == "BHYVE"
    return classify(
        dmi,
        # Only worth the sysfs walk when DMI already says this is bhyve.
        ha_backplane_present=is_bhyve and _bhyve_ha_backplane_present(),
    )


def get_hardware_class() -> HardwareClass:
    """Return the matrix column this system belongs to."""
    return get_hardware_info().hardware_class
