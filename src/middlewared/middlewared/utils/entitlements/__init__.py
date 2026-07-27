"""Pure license-entitlement engine.

Import-safe and stateless: holds no middleware object and performs no I/O.
Every feature's entitlement is a pure function of a small set of facts
(hardware class, HA capability, license) evaluated against a policy.

A policy entry is one of a few rule kinds: a matrix ``Vector`` (resolved by
column against the product feature matrix), a ``LegacyRule`` (an arbitrary
callable reproducing a today-behavior gate verbatim), a ``TierRule`` (gating on
a per-feature ``FeatureInfo.type`` qualifier), or a ``LicenseTypeRule`` (gating
on ``LicenseInfo.type``). The live ``POLICY`` mixes matrix ``Vector``s with a
few remaining ``LegacyRule``s; flipping a feature to its matrix ``Vector`` is a
one-line data change.

Layering is a strict DAG: ``facts`` <- ``engine`` <- ``legacy`` <- ``policy``.
``engine`` is pure evaluation with no knowledge of the live registry; ``policy``
owns the registry and the ``check`` dispatch.
"""

from __future__ import annotations

from .engine import (
    COLUMNS,
    FEATURE_DISPLAY_NAMES,
    FEATURE_MESSAGES,
    DerivedEntitlement,
    Entitlement,
    LegacyRule,
    LicenseTypeRule,
    Reason,
    Rule,
    TierRule,
    Vector,
)
from .facts import EntitlementFacts, HardwareClass
from .matrix import TARGET_VECTORS
from .policy import POLICY, check_entitlement

__all__ = [
    "COLUMNS",
    "FEATURE_DISPLAY_NAMES",
    "FEATURE_MESSAGES",
    "POLICY",
    "TARGET_VECTORS",
    "DerivedEntitlement",
    "Entitlement",
    "EntitlementFacts",
    "HardwareClass",
    "LegacyRule",
    "LicenseTypeRule",
    "Reason",
    "Rule",
    "TierRule",
    "Vector",
    "check_entitlement",
]
