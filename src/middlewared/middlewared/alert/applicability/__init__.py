"""Pure alert-applicability engine.

Whether an alert applies to a system is a pure function of two independent
facts -- what the hardware is, and what the license grants -- evaluated against
a rule the declaration states for itself. ``applies`` takes those facts as an
argument and holds no middleware object, so every declaration in the tree can
be evaluated against synthesized facts.

The two axes are deliberately not conjoined into a single product notion. A
rule is a ``HardwareRule`` (hardware class membership), a ``LicenseRule``
(``LICENSED`` or ``HA``, the latter delegated to the entitlement policy so
there is one definition of HA licensing in the tree), an ``AnyOf`` of those, or
``None`` for the unconstrained case.

Layering is a strict DAG: ``facts`` <- ``engine``, with ``system`` off to the
side importing ``facts`` and imported by nothing else here. Unlike
``utils/entitlements``, the impure entry point ``get_alert_facts`` is **not**
re-exported from this package: ``alert/base.py`` imports this package for the
``Rule`` annotation alone, and re-exporting would make every module that merely
touches ``alert.base`` import the licence-reading path with it. Callers of the
live reader import ``system`` directly.
"""

from __future__ import annotations

from .engine import AnyOf, HardwareRule, LicenseRequirement, LicenseRule, Rule, applies
from .facts import AlertFacts, HardwareClass

__all__ = [
    "AlertFacts",
    "AnyOf",
    "HardwareClass",
    "HardwareRule",
    "LicenseRequirement",
    "LicenseRule",
    "Rule",
    "applies",
]
