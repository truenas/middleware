"""Pure license-entitlement engine.

Holds no middleware object. Every feature's entitlement is a pure function of a
small set of facts (hardware class, license) evaluated against a policy, and
``check_entitlement`` takes those facts as an argument. The one exception is
``get_entitlement``, which reads the license and the chassis to build them for
the running system; it lives in ``system`` and nothing else here imports it, so
the evaluation half stays pure and testable against synthesized facts.

A policy entry is one of a few rule kinds: a matrix ``Vector`` (resolved by
column against the product feature matrix), a ``LegacyRule`` (an arbitrary
callable reproducing a today-behavior gate verbatim), a ``TierRule`` (gating on
a per-feature ``FeatureInfo.type`` qualifier), or a ``LicenseTypeRule`` (gating
on ``LicenseInfo.type``). Every live ``POLICY`` feature is now bound to its
matrix ``Vector``; ``LegacyRule`` is retained as a rule kind for any feature
that later needs a transitional shim. Flipping a feature between the two is a
one-line data change.

Layering is a strict DAG: ``facts`` <- ``engine`` <- ``legacy`` <- ``policy``.
``engine`` is pure evaluation with no knowledge of the live registry; ``policy``
owns the registry and the ``check`` dispatch. ``HardwareClass`` now originates
in ``middlewared.utils.hardware.types`` -- detecting what a machine is is not
an entitlement concern -- and is re-exported here for callers that only ever
deal with it as an ingredient of ``EntitlementFacts``.
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
from .system import get_entitlement

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
    "get_entitlement",
]
