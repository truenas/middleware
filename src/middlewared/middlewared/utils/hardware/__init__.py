"""What machine is this?

One place to ask, so nothing else has to know that the answer comes from DMI,
a chassis tag, or a scsi_generic inquiry. Callers that only care which column
of the product feature matrix a system sits in want ``get_hardware_class``;
callers that need the finer platform distinction want ``get_hardware_info``.

Layering is a strict DAG: ``types`` <- (``classify``, ``detect``) <-
``probe``. ``types`` holds the vocabulary, ``classify`` is pure and takes DMI
as an argument, ``detect`` is the platform team's HA platform/node detector
kept verbatim, and ``probe`` is the single sanctioned impurity -- it reads the
system and runs ``detect``, which is where the caching lives. Nothing here imports
``middlewared.service`` or ``middlewared.utils.entitlements``; entitlements
depends on this package, so the reverse would be a cycle.

``detect`` imports ``middlewared.plugins.enclosure_`` and that is an accepted
exception rather than an oversight: reading SES enclosures is how several iX
platforms report which controller they are, the enumeration code lives in that
plugin package, and duplicating it here to keep the import graph tidy would
give us two copies of hardware facts that must not disagree. That package
imports nothing from ``middlewared.service`` or from this one, so it adds no
cycle.
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
