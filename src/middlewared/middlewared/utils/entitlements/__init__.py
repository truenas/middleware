"""Pure license-entitlement engine.

Holds no middleware object. Every feature's entitlement is a pure function of a
small set of facts (hardware class, license) evaluated against a policy, and
``check_entitlement`` takes those facts as an argument. The exceptions are
``get_facts``, which reads the license and the chassis for the running system,
and ``get_entitlement``, which evaluates the policy against them; both live in
``system`` and nothing else here imports it, so the evaluation half stays pure
and testable against synthesized facts. ``get_facts`` is the single live reader
of the facts in the tree, for entitlement and alert-applicability questions
alike.

A policy entry is one of a few rule kinds: a matrix ``Vector`` (resolved by
column against the product feature matrix), a ``LegacyRule`` (an arbitrary
callable reproducing a today-behavior gate verbatim), a ``TierRule`` (resolved
by column against its ``DERIVED_VECTORS`` row, then qualified by a per-feature
``FeatureInfo.type``), or a ``LicenseTypeRule`` (gating on ``LicenseInfo.type``
alone, with no column). Every live ``POLICY`` feature is now bound to its matrix
``Vector``; ``LegacyRule`` is retained as a rule kind for any feature that later
needs a transitional shim. Flipping a feature between the two is a one-line data
change.

A ``TierRule``'s vector may only set the two key columns, because a tier is read
off a feature key and cannot be evaluated without one; the rule rejects anything
else at construction.

Layering is a strict DAG: ``facts`` <- ``engine`` <- ``legacy`` <- ``policy``.
``engine`` is pure evaluation with no knowledge of the live registry; ``policy``
owns the registry and the ``check`` dispatch. ``HardwareClass`` now originates
in ``middlewared.utils.hardware.types`` -- detecting what a machine is is not
an entitlement concern -- and is re-exported here for callers that only ever
deal with it as an ingredient of ``EntitlementFacts``.
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
