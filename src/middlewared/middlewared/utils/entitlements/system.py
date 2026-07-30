"""Evaluate entitlements for the system this process is running on.

The only module in this package that touches the system: it reads the license
and the chassis. Nothing else here imports it, so the rest of the package stays
pure and the engine can still be evaluated against synthesized facts.

This is the single entry point for a live entitlement question. Callers name a
feature and nothing else; anything that builds ``EntitlementFacts`` by hand is
either a test or a bug.
"""

from __future__ import annotations

from ixhardware import get_chassis_hardware

from middlewared.utils.license import get_license

from .engine import Entitlement
from .facts import EntitlementFacts, HardwareClass
from .policy import check_entitlement

__all__ = ("get_entitlement",)


def get_entitlement(feature: str) -> Entitlement:
    """Return the entitlement for `feature` on this system.

    ``get_chassis_hardware()`` is cheap after the first call in a process:
    ``ixhardware.parse_dmi()`` is ``@cache``d, so only that first call forks
    dmidecode. It is pinned to ``str`` because ixhardware ships no type
    information and would otherwise be ``Any``.
    """
    chassis: str = get_chassis_hardware()
    return check_entitlement(
        feature,
        EntitlementFacts(
            hardware_class=HardwareClass.from_chassis(chassis),
            license=get_license(),
        ),
    )
