from __future__ import annotations

import typing
from types import MappingProxyType

from truenas_pylicensed import LicenseType
from truenas_pylicensed.features import LicenseFeature, SupportTier

from . import legacy
from .engine import (
    DerivedEntitlement,
    Entitlement,
    LegacyRule,
    LicenseTypeRule,
    Rule,
    TierRule,
    _check_license_type,
    _check_tier,
    _check_vector,
)
from .matrix import TARGET_VECTORS

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from .facts import EntitlementFacts


# Live policy. One entry per rule kind currently in active use: matrix
# ``Vector``s where a feature has been flipped onto its product-matrix cells,
# ``LegacyRule``s reproducing today's behavior verbatim for the rest, a
# ``LicenseTypeRule`` for HA, and a ``TierRule`` for proactive support.
POLICY: Mapping[str, Rule] = MappingProxyType(
    {
        LicenseFeature.DEDUP: TARGET_VECTORS[LicenseFeature.DEDUP],
        LicenseFeature.ZFSTIER: TARGET_VECTORS[LicenseFeature.ZFSTIER],
        LicenseFeature.SED: LegacyRule(func=legacy.sed),
        LicenseFeature.NVMEOF_SPDK: LegacyRule(func=legacy.nvmet_spdk),
        DerivedEntitlement.HA: LicenseTypeRule(allowed_types=frozenset({LicenseType.ENTERPRISE_HA})),
        DerivedEntitlement.PROACTIVE_SUPPORT: TierRule(
            feature=LicenseFeature.SUPPORT,
            allowed_tiers=frozenset({SupportTier.GOLD, SupportTier.SILVER, SupportTier.SILVERINTERNATIONAL}),
        ),
    }
)


def check_entitlement(
    feature: str,
    facts: EntitlementFacts,
    *,
    policy: Mapping[str, Rule] | None = None,
) -> Entitlement:
    rules = POLICY if policy is None else policy
    try:
        rule = rules[feature]
    except KeyError:
        raise ValueError(f"Unknown feature: {feature!r}")

    if isinstance(rule, LegacyRule):
        return rule.func(facts)
    if isinstance(rule, TierRule):
        return _check_tier(feature, rule, facts)
    if isinstance(rule, LicenseTypeRule):
        return _check_license_type(feature, rule, facts)
    return _check_vector(feature, rule, facts)
