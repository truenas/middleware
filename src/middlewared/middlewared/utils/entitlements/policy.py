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


# Only ``Vector`` and ``TierRule`` *decide* by matrix cell, the latter against DERIVED_VECTORS
# with the tier as a further qualifier. ``LicenseTypeRule`` reports a column but decides on
# ``LicenseInfo.type`` alone -- see the HA entry below.
POLICY: Mapping[str, Rule] = MappingProxyType(
    {
        LicenseFeature.APPS: TARGET_VECTORS[LicenseFeature.APPS],
        LicenseFeature.CATALOG_ENTERPRISE_TRAIN: TARGET_VECTORS[LicenseFeature.CATALOG_ENTERPRISE_TRAIN],
        LicenseFeature.CONTAINERS: TARGET_VECTORS[LicenseFeature.CONTAINERS],
        LicenseFeature.DEDUP: TARGET_VECTORS[LicenseFeature.DEDUP],
        LicenseFeature.DIRECTORY_SERVICES_AUTH: TARGET_VECTORS[LicenseFeature.DIRECTORY_SERVICES_AUTH],
        LicenseFeature.FIBRECHANNEL: TARGET_VECTORS[LicenseFeature.FIBRECHANNEL],
        # TODO: KMIP needs webui ticket as well to remove/update gate
        LicenseFeature.KMIP: TARGET_VECTORS[LicenseFeature.KMIP],
        LicenseFeature.MISSION_CRITICAL: TARGET_VECTORS[LicenseFeature.MISSION_CRITICAL],
        LicenseFeature.NETWORK_FEC: TARGET_VECTORS[LicenseFeature.NETWORK_FEC],
        LicenseFeature.NFS_SNAPSHOT: TARGET_VECTORS[LicenseFeature.NFS_SNAPSHOT],
        LicenseFeature.NVMEOF_SPDK: TARGET_VECTORS[LicenseFeature.NVMEOF_SPDK],
        LicenseFeature.RDMA: TARGET_VECTORS[LicenseFeature.RDMA],
        LicenseFeature.SED: TARGET_VECTORS[LicenseFeature.SED],
        LicenseFeature.SMB_FASTPATH: TARGET_VECTORS[LicenseFeature.SMB_FASTPATH],
        LicenseFeature.SMB_VEEAM: TARGET_VECTORS[LicenseFeature.SMB_VEEAM],
        LicenseFeature.STIG: TARGET_VECTORS[LicenseFeature.STIG],
        LicenseFeature.SUPPORT: TARGET_VECTORS[LicenseFeature.SUPPORT],
        LicenseFeature.TRUESEARCH: TARGET_VECTORS[LicenseFeature.TRUESEARCH],
        LicenseFeature.VMS: TARGET_VECTORS[LicenseFeature.VMS],
        # TODO: See if we should have runtime gates as well and not just config gates
        LicenseFeature.WEBSHARE: TARGET_VECTORS[LicenseFeature.WEBSHARE],
        LicenseFeature.ZFSTIER: TARGET_VECTORS[LicenseFeature.ZFSTIER],
        # Do not wire the product matrix's "HA Functionality" row up. HA is a license *type*,
        # not a feature key, so there is no LicenseFeature.HA to look up and the HW+K/CE+K
        # columns are meaningless for it: only LicenseInfo.type can decide. Honouring the row
        # literally would grant HA to any licensed appliance, ENTERPRISE_SINGLE included, and
        # withdraw it from test-licensed pairs that are not iX hardware.
        DerivedEntitlement.HA: LicenseTypeRule(allowed_types=frozenset({LicenseType.ENTERPRISE_HA})),
        # The vector grants nothing the tier check would not also reach, but it decides the denial
        # reason on the unlicensed columns, and it is what makes a one-sided row take effect.
        DerivedEntitlement.PROACTIVE_SUPPORT: TierRule(
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
