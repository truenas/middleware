from __future__ import annotations

import typing
from types import MappingProxyType

from truenas_pylicensed import LicenseType
from truenas_pylicensed.features import LicenseFeature, SupportTier

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
from .matrix import DERIVED_VECTORS, TARGET_VECTORS

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from .facts import EntitlementFacts


# Live policy. Every feature resolves against its product-matrix cells as a
# ``Vector``; the two derived entitlements that are not per-feature keys use a
# ``LicenseTypeRule`` for HA and a ``TierRule`` for proactive support. The
# ``LegacyRule`` kind is still supported by the dispatch below but unused here.
#
# Only two of the four kinds resolve by matrix column, and the split is deliberate:
# ``Vector`` and ``TierRule`` do, the latter against DERIVED_VECTORS with the tier as a
# further qualifier. ``LicenseTypeRule`` does not -- see the HA entry below -- and a
# ``LegacyRule``'s callable is the whole rule by definition. This is settled, not a
# migration someone left half finished.
POLICY: Mapping[str, Rule] = MappingProxyType(
    {
        LicenseFeature.APPS: TARGET_VECTORS[LicenseFeature.APPS],
        LicenseFeature.CATALOG_ENTERPRISE_TRAIN: TARGET_VECTORS[LicenseFeature.CATALOG_ENTERPRISE_TRAIN],
        LicenseFeature.CONTAINERS: TARGET_VECTORS[LicenseFeature.CONTAINERS],
        LicenseFeature.DEDUP: TARGET_VECTORS[LicenseFeature.DEDUP],  # TODO: Validate logic with old impl
        LicenseFeature.DIRECTORY_SERVICES: TARGET_VECTORS[LicenseFeature.DIRECTORY_SERVICES],
        LicenseFeature.FIBRECHANNEL: TARGET_VECTORS[LicenseFeature.FIBRECHANNEL],
        # TODO: KMIP needs webui ticket as well to remove/update gate
        LicenseFeature.KMIP: TARGET_VECTORS[LicenseFeature.KMIP],
        LicenseFeature.NETWORK_FEC: TARGET_VECTORS[LicenseFeature.NETWORK_FEC],
        LicenseFeature.NFS_SNAPSHOT: TARGET_VECTORS[LicenseFeature.NFS_SNAPSHOT],
        LicenseFeature.NVMEOF_SPDK: TARGET_VECTORS[LicenseFeature.NVMEOF_SPDK],
        LicenseFeature.RDMA: TARGET_VECTORS[LicenseFeature.RDMA],
        LicenseFeature.SED: TARGET_VECTORS[LicenseFeature.SED],
        LicenseFeature.SMB_FASTPATH: TARGET_VECTORS[LicenseFeature.SMB_FASTPATH],
        LicenseFeature.SMB_VEEAM: TARGET_VECTORS[LicenseFeature.SMB_VEEAM],
        LicenseFeature.STIG: TARGET_VECTORS[LicenseFeature.STIG],
        # TODO: SUPPORT is injected into every legacy license, so on the installed base this
        # grants wherever a license exists at all. Revisit which populations that hands access
        # to before this ships: freenas-model and Mini licensees now route their support
        # tickets to the enterprise endpoint instead of the community one, and an unlicensed
        # HA-capable system moves the other way.
        LicenseFeature.SUPPORT: TARGET_VECTORS[LicenseFeature.SUPPORT],
        LicenseFeature.TRUESEARCH: TARGET_VECTORS[LicenseFeature.TRUESEARCH],
        LicenseFeature.VMS: TARGET_VECTORS[LicenseFeature.VMS],
        # TODO: See if we should have runtime gates as well and not just config gates
        LicenseFeature.WEBSHARE: TARGET_VECTORS[LicenseFeature.WEBSHARE],
        # TODO: Validate logic with old impl / Remember that zfstier client has license
        # logic as well which should be reviewed too
        LicenseFeature.ZFSTIER: TARGET_VECTORS[LicenseFeature.ZFSTIER],
        # HA is a license *type*, not a feature key, so it deliberately has no vector in
        # either matrix map. There is no LicenseFeature.HA to look up, which makes the
        # HW+K/CE+K columns meaningless for it: only LicenseInfo.type can decide. The
        # product matrix does carry an "HA Functionality" row, and it is knowingly not
        # honoured -- taken literally it would grant HA to any licensed appliance,
        # ENTERPRISE_SINGLE included, and would withdraw it from the test-licensed pairs
        # that are not iX hardware. Do not wire it up.
        DerivedEntitlement.HA: LicenseTypeRule(allowed_types=frozenset({LicenseType.ENTERPRISE_HA})),
        # The vector is key-only, so it grants nothing the tier check would not also reach;
        # it is what makes a future one-sided row (say, appliances but not keyed Minis)
        # actually take effect instead of being silently ignored.
        DerivedEntitlement.PROACTIVE_SUPPORT: TierRule(  # TODO: Validate logic with old impl
            feature=LicenseFeature.SUPPORT,
            allowed_tiers=frozenset({SupportTier.GOLD, SupportTier.SILVER, SupportTier.SILVERINTERNATIONAL}),
            vector=DERIVED_VECTORS[DerivedEntitlement.PROACTIVE_SUPPORT],
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
