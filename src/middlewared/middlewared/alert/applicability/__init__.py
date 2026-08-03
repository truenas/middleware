"""Pure alert-applicability engine.

Whether an alert applies to a system is a pure function of two independent facts -- what
the hardware is, and what the license grants -- evaluated against a rule the declaration
states for itself. ``applies`` takes those facts as an argument and holds no middleware
object, so every declaration in the tree can be evaluated against synthesized facts.

A rule is a predicate over the facts, or ``None`` for the unconstrained case. Nothing
introspects a rule's structure, so there is none to introspect: a population is a function,
the same shape a feature flag has, and the two can be the same object. Declarations do not
build rules, they name a population from ``vocabulary``, which is where the set of
distinctions worth making is decided.

The facts are ``EntitlementFacts``. An applicability question and an entitlement question
rest on the same two facts, so there is one shape for them, no conversion between them, and
one live reader -- ``middlewared.utils.entitlements.get_facts``, which reads the license and
the chassis and is deliberately uncached. ``Applicability`` is the one place that reading is
turned into answers: it takes facts, memoizes per declaration, and is what callers hold
rather than a rule and a set of facts they each evaluate for themselves.

Layering is a strict DAG: ``engine`` <- ``vocabulary`` <- ``snapshot``.
"""

from __future__ import annotations

from .engine import (
    Declaration,
    ListedDeclaration,
    Rule,
    applies,
    applies_for_listing,
    declaration_rule_name,
    rule_name,
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
)

__all__ = [
    "ANY_LICENSE",
    "APPLIANCE_OR_HA_LICENSED",
    "EXPECTED_TO_BE_LICENSED",
    "HA_LICENSED",
    "MINI_HARDWARE",
    "NOT_APPLIANCE_HARDWARE",
    "TRUENAS_HARDWARE",
    "Applicability",
    "Declaration",
    "ListedDeclaration",
    "Rule",
    "applies",
    "applies_for_listing",
    "declaration_rule_name",
    "rule_name",
]
