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
        LicenseFeature.APPS: TARGET_VECTORS[LicenseFeature.APPS],
        LicenseFeature.CONTAINERS: TARGET_VECTORS[LicenseFeature.CONTAINERS],
        LicenseFeature.DEDUP: TARGET_VECTORS[LicenseFeature.DEDUP],  # TODO: Validate logic with old impl
        LicenseFeature.DIRECTORY_SERVICES: TARGET_VECTORS[LicenseFeature.DIRECTORY_SERVICES],
        LicenseFeature.FIBRECHANNEL: TARGET_VECTORS[LicenseFeature.FIBRECHANNEL],
        # TODO: JBOF is the only entry in this policy whose vector has ce_k = 0, so a system whose chassis
        # does not detect as TrueNAS hardware is denied even when its license carries the key and lists the
        # shelves. Confirm that against product intent.
        # TODO: The gate this replaced never consulted a feature key at all. Check licenses in the field to
        # confirm no system that could attach a shelf before is denied now. Two shapes to look for: a license
        # that would land on the CE side with a license but no key, and a license whose additional-hardware
        # list repeats the ES24N code, since the enclosure counts are built last-wins rather than summed, so
        # a trailing zero-quantity entry would leave the count at zero and suppress the injected key.
        LicenseFeature.JBOF: TARGET_VECTORS[LicenseFeature.JBOF],
        LicenseFeature.NETWORK_FEC: TARGET_VECTORS[LicenseFeature.NETWORK_FEC],
        LicenseFeature.NFS_SNAPSHOT: TARGET_VECTORS[LicenseFeature.NFS_SNAPSHOT],
        LicenseFeature.NVMEOF_SPDK: TARGET_VECTORS[LicenseFeature.NVMEOF_SPDK],
        LicenseFeature.RDMA: TARGET_VECTORS[LicenseFeature.RDMA],
        LicenseFeature.SED: LegacyRule(func=legacy.sed),  # TODO: Validate logic with old impl
        LicenseFeature.SMB_FASTPATH: TARGET_VECTORS[LicenseFeature.SMB_FASTPATH],
        LicenseFeature.SMB_VEEAM: TARGET_VECTORS[LicenseFeature.SMB_VEEAM],
        LicenseFeature.STIG: TARGET_VECTORS[LicenseFeature.STIG],
        LicenseFeature.TRUESEARCH: TARGET_VECTORS[LicenseFeature.TRUESEARCH],
        LicenseFeature.VMS: TARGET_VECTORS[LicenseFeature.VMS],
        # TODO: Validate logic with old impl / Remember that zfstier client has license
        # logic as well which should be reviewed too
        LicenseFeature.ZFSTIER: TARGET_VECTORS[LicenseFeature.ZFSTIER],
        # TODO: Validate logic with old impl
        DerivedEntitlement.HA: LicenseTypeRule(allowed_types=frozenset({LicenseType.ENTERPRISE_HA})),
        DerivedEntitlement.PROACTIVE_SUPPORT: TierRule(  # TODO: Validate logic with old impl
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
