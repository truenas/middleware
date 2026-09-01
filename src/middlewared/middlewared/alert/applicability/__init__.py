"""Pure alert-applicability engine.

Whether an alert applies to a system is a pure function of two independent facts -- what
the hardware is, and what the license grants -- evaluated against a rule the declaration
states for itself. ``applies`` takes those facts as an argument and holds no middleware
object, so every declaration in the tree can be evaluated against synthesized facts.

The facts are ``EntitlementFacts``, the same shape an entitlement question is asked in, so
there is no conversion between the two.
"""

from __future__ import annotations

from .engine import (
    Rule,
    applies,
    applies_for_listing,
    declaration_rule_name,
)
from .snapshot import Applicability
from .vocabulary import (
    ANY_LICENSE,
    APPLIANCE_OR_HA_LICENSED,
    EXPECTED_TO_BE_LICENSED,
    HA_LICENSED,
    MINI_HARDWARE,
    NOT_APPLIANCE_HARDWARE,
    TRUENAS_HARDWARE,
    TRUENAS_OR_MINI_HARDWARE,
)

__all__ = [
    "ANY_LICENSE",
    "APPLIANCE_OR_HA_LICENSED",
    "EXPECTED_TO_BE_LICENSED",
    "HA_LICENSED",
    "MINI_HARDWARE",
    "NOT_APPLIANCE_HARDWARE",
    "TRUENAS_HARDWARE",
    "TRUENAS_OR_MINI_HARDWARE",
    "Applicability",
    "Rule",
    "applies",
    "applies_for_listing",
    "declaration_rule_name",
]
