"""Pure alert-applicability engine.

Whether an alert applies to a system is a pure function of two independent facts -- what
the hardware is, and what the license grants -- evaluated against a rule the declaration
states for itself. ``applies`` takes those facts as an argument and holds no middleware
object, so every declaration in the tree can be evaluated against synthesized facts.

The two axes are deliberately not conjoined into a single product notion. A rule is a
``HardwareRule`` (hardware class membership), a ``LicensePresentRule`` (a license exists at
all), an ``EntitlementRule`` (the entitlement policy grants a named feature, so a feature is
defined once for the whole tree), an ``AnyOf`` or ``AllOf`` of those, or ``None`` for the
unconstrained case. Declarations do not build rules: they name a population from
``vocabulary``, which is where the set of distinctions worth making is decided.

The facts are ``EntitlementFacts``. An applicability question and an entitlement question
rest on the same two facts, so there is one shape for them, no conversion between them, and
one live reader -- ``middlewared.utils.entitlements.get_facts``, which reads the license and
the chassis and is deliberately uncached.

Layering is a strict DAG: ``engine`` <- ``vocabulary``.
"""

from __future__ import annotations

from .engine import (
    AllOf,
    AnyOf,
    EntitlementRule,
    HardwareRule,
    LicensePresentRule,
    ListedDeclaration,
    Rule,
    applies,
    applies_for_listing,
)
from .vocabulary import (
    ANY_LICENSE,
    APPLIANCE_OR_HA_LICENSED,
    EXPECTED_TO_BE_LICENSED,
    HA_LICENSED,
    MINI_HARDWARE,
    NOT_APPLIANCE_HARDWARE,
    TRUENAS_HARDWARE,
)

__all__ = [
    "ANY_LICENSE",
    "APPLIANCE_OR_HA_LICENSED",
    "EXPECTED_TO_BE_LICENSED",
    "HA_LICENSED",
    "MINI_HARDWARE",
    "NOT_APPLIANCE_HARDWARE",
    "TRUENAS_HARDWARE",
    "AllOf",
    "AnyOf",
    "EntitlementRule",
    "HardwareRule",
    "LicensePresentRule",
    "ListedDeclaration",
    "Rule",
    "applies",
    "applies_for_listing",
]
