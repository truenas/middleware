"""Pure license-entitlement engine.

Holds no middleware object: a feature's entitlement is a function of a small set of facts
(hardware class, license) evaluated against a policy. Only ``system`` reads the live machine,
and the layering that keeps it out of the evaluation half is enforced by the
``entitlements_layers`` import contract in ``src/middlewared/setup.cfg``.

A policy entry is one of a few rule kinds: a matrix ``Vector`` (resolved by column against the
product feature matrix), a ``LegacyRule`` (an arbitrary callable reproducing a today-behavior
gate verbatim), a ``TierRule`` (resolved by column against its ``DERIVED_VECTORS`` row, then
qualified by a per-feature ``FeatureInfo.type``), or a ``LicenseTypeRule`` (decided on
``LicenseInfo.type`` alone).

A ``TierRule``'s vector may only set the two key columns, because a tier is read off a feature
key and cannot be evaluated without one; the rule rejects anything else at construction.

``HardwareClass`` is re-exported here for callers that only ever deal with it as an ingredient
of ``EntitlementFacts``.
"""

from __future__ import annotations

from truenas_pylicensed.features import LicenseFeature

from .engine import (
    COLUMNS,
    FEATURE_DISPLAY_NAMES,
    FEATURE_MESSAGES,
    DerivedEntitlement,
    Entitlement,
    EntitlementKey,
    LegacyRule,
    LicenseTypeRule,
    Reason,
    Rule,
    TierRule,
    Vector,
)
from .facts import EntitlementFacts, HardwareClass
from .matrix import DERIVED_VECTORS, TARGET_VECTORS
from .policy import POLICY, check_entitlement
from .system import get_entitlement, get_facts

__all__ = [
    "COLUMNS",
    "DERIVED_VECTORS",
    "FEATURE_DISPLAY_NAMES",
    "FEATURE_MESSAGES",
    "POLICY",
    "TARGET_VECTORS",
    "DerivedEntitlement",
    "Entitlement",
    "EntitlementFacts",
    "EntitlementKey",
    "HardwareClass",
    "LegacyRule",
    "LicenseFeature",
    "LicenseTypeRule",
    "Reason",
    "Rule",
    "TierRule",
    "Vector",
    "check_entitlement",
    "get_entitlement",
    "get_facts",
]
