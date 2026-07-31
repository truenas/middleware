from datetime import date

import pytest

from truenas_pylicensed import LicenseType
from truenas_pylicensed.features import LicenseFeature, SupportTier

from middlewared.utils.entitlements import (
    DerivedEntitlement,
    EntitlementFacts,
    HardwareClass,
    Reason,
    check_entitlement,
)
from middlewared.utils.license import FeatureInfo, LicenseInfo, parse_legacy_license


def _features(names, *, support_type=None, start=date(2026, 4, 8), end=date(2026, 4, 30)):
    """Build the FeatureInfo mapping a legacy license translates to, in order."""
    return {
        name: FeatureInfo(
            name=name,
            start_date=start,
            expires_at=end,
            source="enterprise",
            type=support_type if name == "SUPPORT" else None,
        )
        for name in names
    }


# Mirrors the production injection bucket that fires for every parseable legacy
# blob, in LicenseFeature declaration order. Injected flags are appended after
# the license's own bits, also in declaration order.
_ALL_LEGACY_INJECT = [
    "APPS",
    "CONTAINERS",
    "DIRECTORY_SERVICES",
    "KMIP",
    "NETWORK_FEC",
    "NFS_SNAPSHOT",
    "NVMEOF_SPDK",
    "RDMA",
    "STIG",
    "SUPPORT",
    "TRUESEARCH",
    "VMS",
    "WEBSHARE",
]


@pytest.mark.parametrize(
    "text,result",
    [
        # Enterprise HA license (H10, GOLD contract): FibreChannel + VM bits, proactive
        # SUPPORT, plus the all-legacy and enterprise-only injected flags.
        (
            "AUgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAVEVTVC0wMDAwMDIAAAAAAAQAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
            "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAAAAAAAgMCAgE=",
            LicenseInfo(
                id="legacy_TEST-000001",
                type=LicenseType.ENTERPRISE_HA,
                model="H10",
                support_expires_at=date(2026, 4, 30),
                license_expires_at=None,
                features=_features(
                    [
                        "FIBRECHANNEL",
                        "VMS",
                        "SUPPORT",
                        "APPS",
                        "AUTOTUNE",
                        "CATALOG_ENTERPRISE_TRAIN",
                        "CONTAINERS",
                        "DIRECTORY_SERVICES",
                        "KMIP",
                        "MISSION_CRITICAL",
                        "NETWORK_FEC",
                        "NFS_SNAPSHOT",
                        "NVMEOF_SPDK",
                        "RDMA",
                        "SMB_FASTPATH",
                        "SMB_VEEAM",
                        "STIG",
                        "TRUESEARCH",
                        "WEBSHARE",
                    ],
                    support_type="GOLD",
                ),
                serials=("TEST-000001", "TEST-000002"),
                enclosures={"E24": 3, "E16": 2},
                contract_type="GOLD",
            ),
        ),
        # Enterprise single license (X10, STANDARD contract): jails->APPS bit, plus the
        # all-legacy and enterprise-only injected flags. STANDARD is not a support tier,
        # so the injected SUPPORT flag is stamped BRONZE.
        (
            "AVgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
            "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAA==",
            LicenseInfo(
                id="legacy_TEST-000001",
                type=LicenseType.ENTERPRISE_SINGLE,
                model="X10",
                support_expires_at=date(2026, 4, 30),
                license_expires_at=None,
                features=_features(
                    [
                        "APPS",
                        "AUTOTUNE",
                        "CATALOG_ENTERPRISE_TRAIN",
                        "CONTAINERS",
                        "DIRECTORY_SERVICES",
                        "KMIP",
                        "MISSION_CRITICAL",
                        "NETWORK_FEC",
                        "NFS_SNAPSHOT",
                        "NVMEOF_SPDK",
                        "RDMA",
                        "SMB_FASTPATH",
                        "SMB_VEEAM",
                        "STIG",
                        "SUPPORT",
                        "TRUESEARCH",
                        "VMS",
                        "WEBSHARE",
                    ],
                    support_type="BRONZE",
                ),
                serials=("TEST-000001",),
                enclosures={},
                contract_type="STANDARD",
            ),
        ),
        # freenascertified license (freenas-prefixed model): only the all-legacy
        # bucket injects; no enterprise-only flags. FREENASCERTIFIED is not a support
        # tier, so the injected SUPPORT flag is stamped BRONZE.
        (
            "AUZSRUVOQVMtTUlOSQAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAUAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1z"
            "IEluYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==",
            LicenseInfo(
                id="legacy_TEST-000001",
                type=LicenseType.ENTERPRISE_SINGLE,
                model="FREENAS-MINI",
                support_expires_at=date(2026, 4, 30),
                license_expires_at=None,
                features=_features(_ALL_LEGACY_INJECT, support_type="BRONZE"),
                serials=("TEST-000001",),
                enclosures={},
                contract_type="FREENASCERTIFIED",
            ),
        ),
    ],
)
def test__parse_legacy_license(text, result):
    assert parse_legacy_license(text) == result


# A legacy blob carries no license type of its own: the second (HA) serial is the only
# thing that distinguishes an HA license from a single-head one, and it is what the
# translation turns into LicenseType.
@pytest.mark.parametrize(
    "text,type_",
    [
        # H10 with system_serial_ha = TEST-000002.
        (
            "AUgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAVEVTVC0wMDAwMDIAAAAAAAQAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
            "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAAAAAAAgMCAgE=",
            LicenseType.ENTERPRISE_HA,
        ),
        # X10 with an empty system_serial_ha field.
        (
            "AVgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
            "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAA==",
            LicenseType.ENTERPRISE_SINGLE,
        ),
    ],
)
def test__parse_legacy_license_ha_type(text, type_):
    assert parse_legacy_license(text).type is type_


# X10, BRONZE contract, single head -- the same shape as the STANDARD blob above with
# the contract type byte changed.
LEGACY_BRONZE_BLOB = (
    "AVgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
    "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAA=="
)


# Interlock between the unconditional SUPPORT injection and the tier gate. SUPPORT is
# injected into every legacy license, so the tier stamped on that injected key is the
# only thing keeping proactive support away from the whole legacy installed base. Both
# halves are asserted together: the key must be present (so anything gating on the key
# alone keeps working) and proactive support must still be denied. If a later change
# makes the tier gate tier-blind, or stops stamping BRONZE on contract types that never
# bought proactive support, this fails rather than silently granting it to everyone.
def test__legacy_bronze_gets_support_key_but_not_proactive_support():
    info = parse_legacy_license(LEGACY_BRONZE_BLOB)
    assert info.has_feature(LicenseFeature.SUPPORT)
    assert info.feature_type(LicenseFeature.SUPPORT) == SupportTier.BRONZE

    facts = EntitlementFacts(hardware_class=HardwareClass.TRUENAS_HW, license=info)
    assert check_entitlement(LicenseFeature.SUPPORT, facts).entitled is True

    proactive = check_entitlement(DerivedEntitlement.PROACTIVE_SUPPORT, facts)
    assert proactive.entitled is False
    assert proactive.reason == Reason.TIER_INSUFFICIENT


# The same interlock for the contract types that are not support tiers at all: they
# collapse to BRONZE rather than stamping a value the tier gate has never heard of.
@pytest.mark.parametrize(
    "text",
    [
        # X10, STANDARD contract.
        "AVgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1z"
        "IEluYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAA==",
        # FREENAS-MINI, FREENASCERTIFIED contract.
        "AUZSRUVOQVMtTUlOSQAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAUAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1z"
        "IEluYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==",
    ],
)
def test__legacy_non_tier_contract_types_get_no_proactive_support(text):
    info = parse_legacy_license(text)
    assert info.feature_type(LicenseFeature.SUPPORT) == SupportTier.BRONZE

    facts = EntitlementFacts(hardware_class=HardwareClass.TRUENAS_HW, license=info)
    proactive = check_entitlement(DerivedEntitlement.PROACTIVE_SUPPORT, facts)
    assert proactive.entitled is False
    assert proactive.reason == Reason.TIER_INSUFFICIENT


# The contrast case: a gold contract still gets proactive support, so the interlock
# above is not passing merely because the gate denies everything.
def test__legacy_gold_contract_keeps_proactive_support():
    info = parse_legacy_license(
        "AUgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAVEVTVC0wMDAwMDIAAAAAAAQAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1z"
        "IEluYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAAAAAAAgMCAgE="
    )
    assert info.feature_type(LicenseFeature.SUPPORT) == SupportTier.GOLD

    facts = EntitlementFacts(hardware_class=HardwareClass.TRUENAS_HW, license=info)
    assert check_entitlement(DerivedEntitlement.PROACTIVE_SUPPORT, facts).entitled is True
