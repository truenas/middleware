"""What machine is this?

One place to ask, so nothing else has to know that the answer comes from DMI,
a chassis tag, or a scsi_generic inquiry.

Nothing here imports ``middlewared.service`` or
``middlewared.utils.entitlements``; entitlements depends on this package, so
the reverse would be a cycle.

``detect`` imports the single submodule
``middlewared.plugins.enclosure_.ses_enclosures2``, whose transitive imports
reach neither of those.
"""

from __future__ import annotations

from .classify import classify, classify_platform, hardware_class_for
from .detect import detect_platform
from .probe import get_hardware_class, get_hardware_info
from .types import HardwareClass, HardwareInfo, Platform

__all__ = [
    "HardwareClass",
    "HardwareInfo",
    "Platform",
    "classify",
    "classify_platform",
    "detect_platform",
    "get_hardware_class",
    "get_hardware_info",
    "hardware_class_for",
]
