"""What machine is this?

One place to ask, so nothing else has to know that the answer comes from DMI,
a chassis tag, or a scsi_generic inquiry. Callers that only care which column
of the product feature matrix a system sits in want ``get_hardware_class``;
callers that need the finer platform distinction want ``get_hardware_info``.

Layering is a strict DAG: ``types`` <- ``classify`` <- ``probe``. ``types``
holds the vocabulary, ``classify`` is pure and takes DMI as an argument, and
``probe`` is the single sanctioned impurity -- it reads the system and caches
what it found. Nothing here imports ``middlewared.service`` or
``middlewared.utils.entitlements``; entitlements depends on this package, so
the reverse would be a cycle.
"""

from __future__ import annotations

from .classify import classify, classify_platform, hardware_class_for
from .probe import get_hardware_class, get_hardware_info
from .types import HardwareClass, HardwareInfo, Platform

__all__ = [
    "HardwareClass",
    "HardwareInfo",
    "Platform",
    "classify",
    "classify_platform",
    "get_hardware_class",
    "get_hardware_info",
    "hardware_class_for",
]
