"""Evaluate entitlements for the system this process is running on.

This module reads the license and asks ``middlewared.utils.hardware`` what this machine is. No
evaluation module imports it -- the ``entitlements_layers`` import contract in
``src/middlewared/setup.cfg`` enforces that -- so the engine stays testable against synthesized
facts.

``get_entitlement`` is the entry point for a single live entitlement question. ``get_facts`` is
public so that a caller answering many features at once can read the facts once instead of once
per feature.
"""

from __future__ import annotations

from middlewared.utils.hardware import get_hardware_class
from middlewared.utils.license import get_license

from .engine import Entitlement, EntitlementKey
from .facts import EntitlementFacts
from .policy import check_entitlement

__all__ = ("get_entitlement", "get_facts")


def get_facts() -> EntitlementFacts:
    """Read what this system is, right now.

    Deliberately not cached, because the license has to be re-read each time. Hardware detection
    memoizes itself, so only the first call in a process pays for it.
    """
    return EntitlementFacts(hardware_class=get_hardware_class(), license=get_license())


def get_entitlement(feature: EntitlementKey | str) -> Entitlement:
    """Return the entitlement for `feature` on this system.

    A plain `str` is accepted because the public API cannot name the vocabulary: the import
    contract keeps the engine out of ``middlewared.api.v*``. An unruled key still raises.
    """
    return check_entitlement(feature, get_facts())
