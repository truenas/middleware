import base64
from datetime import date
from unittest.mock import mock_open, patch

import pytest

from licenselib.license import Features
from truenas_pylicensed import FEATURE_NAME_MAP, LicenseType
from truenas_pylicensed.features import LicenseFeature, SupportTier

from middlewared.utils.entitlements import (
    POLICY,
    DerivedEntitlement,
    EntitlementFacts,
    HardwareClass,
    Reason,
    check_entitlement,
)
from middlewared.utils.license import (
    FeatureInfo,
    LicenseInfo,
    get_legacy_license_info,
    parse_legacy_license,
)
from middlewared.utils.license.legacy import _LEGACY_INJECT as _LEGACY_INJECT_SET


def _features(names, *, support_type=None, start=date(2026, 4, 8), end=date(2026, 4, 30)):
    """Build the FeatureInfo mapping a legacy license translates to, in order."""
    return {
        name: FeatureInfo(
            name=name,
            start_date=start if name == "SUPPORT" else None,
            expires_at=end if name == "SUPPORT" else None,
            source="enterprise",
            type=support_type if name == "SUPPORT" else None,
        )
        for name in names
    }


# Derived from the production injection set rather than copied, so the expectations below
# cannot drift from it; test__legacy_injection_set_is_pinned is what keeps that non-vacuous.
_LEGACY_INJECT = [f.value for f in LicenseFeature if f in _LEGACY_INJECT_SET]

# H10, GOLD contract, HA pair. Carries the FibreChannel and VM feature bits.
H10_HA_BLOB = (
    "AUgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAVEVTVC0wMDAwMDIAAAAAAAQAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
    "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAAAAAAAgMCAgE="
)

# X10, STANDARD contract, single head.
X10_BLOB = (
    "AVgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
    "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAA=="
)

# FREENAS-MINI, FREENASCERTIFIED contract, single head.
FREENAS_MINI_BLOB = (
    "AUZSRUVOQVMtTUlOSQAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAUAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1z"
    "IEluYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
)


@pytest.mark.parametrize(
    "text,result",
    [
        # Enterprise HA license (H10, GOLD contract): FibreChannel + VM bits, proactive
        # SUPPORT, plus everything the legacy translation injects.
        (
            H10_HA_BLOB,
            LicenseInfo(
                id="legacy_TEST-000001",
                type=LicenseType.ENTERPRISE_HA,
                model="H10",
                support_expires_at=date(2026, 4, 30),
                features=_features(
                    [
                        "FIBRECHANNEL",
                        "VMS",
                        "SUPPORT",
                        "APPS",
                        "AUTOTUNE",
                        "CATALOG_ENTERPRISE_TRAIN",
                        "CONTAINERS",
                        "DIRECTORY_SERVICES_AUTH",
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
        # Enterprise single license (X10, STANDARD contract): the jails->APPS bit is
        # already in the injection set, so the whole feature list is the injection set.
        # STANDARD is not a support tier, so the injected SUPPORT flag is stamped BRONZE.
        (
            X10_BLOB,
            LicenseInfo(
                id="legacy_TEST-000001",
                type=LicenseType.ENTERPRISE_SINGLE,
                model="X10",
                support_expires_at=date(2026, 4, 30),
                features=_features(_LEGACY_INJECT, support_type="BRONZE"),
                serials=("TEST-000001",),
                enclosures={},
                contract_type="STANDARD",
            ),
        ),
    ],
)
def test__parse_legacy_license(text, result):
    assert parse_legacy_license(text) == result


# X10, BRONZE contract, single head -- the same shape as the STANDARD blob above with
# the contract type byte changed.
LEGACY_BRONZE_BLOB = (
    "AVgxMAAAAAAAAAAAAAAAAABURVNULTAwMDAwMQAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAADIwMjYwNDA4AAAAABYAAAAAAAAAaVhzeXN0ZW1zIE"
    "luYy4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAA=="
)


# SUPPORT is injected into every legacy license, so the tier stamped on that injected key is
# the only thing keeping proactive support from the whole legacy installed base.
def test__legacy_bronze_gets_support_key_but_not_proactive_support():
    info = parse_legacy_license(LEGACY_BRONZE_BLOB)
    assert info.has_feature(LicenseFeature.SUPPORT)
    assert info.feature_type(LicenseFeature.SUPPORT) == SupportTier.BRONZE

    facts = EntitlementFacts(hardware_class=HardwareClass.TRUENAS_HW, license=info)
    assert check_entitlement(LicenseFeature.SUPPORT, facts).entitled is True

    proactive = check_entitlement(DerivedEntitlement.PROACTIVE_SUPPORT, facts)
    assert proactive.entitled is False
    assert proactive.reason == Reason.TIER_INSUFFICIENT


# The same interlock for a contract type that is not a support tier at all: it collapses to
# BRONZE rather than stamping a value the tier gate has never heard of.
def test__legacy_non_tier_contract_types_get_no_proactive_support():
    info = parse_legacy_license(FREENAS_MINI_BLOB)
    assert info.feature_type(LicenseFeature.SUPPORT) == SupportTier.BRONZE

    facts = EntitlementFacts(hardware_class=HardwareClass.TRUENAS_HW, license=info)
    proactive = check_entitlement(DerivedEntitlement.PROACTIVE_SUPPORT, facts)
    assert proactive.entitled is False
    assert proactive.reason == Reason.TIER_INSUFFICIENT


# Positive control, so the interlock is not passing merely because the gate denies everything.
def test__legacy_gold_contract_keeps_proactive_support():
    info = parse_legacy_license(H10_HA_BLOB)
    assert info.feature_type(LicenseFeature.SUPPORT) == SupportTier.GOLD

    facts = EntitlementFacts(hardware_class=HardwareClass.TRUENAS_HW, license=info)
    assert check_entitlement(DerivedEntitlement.PROACTIVE_SUPPORT, facts).entitled is True


def _legacy_info_for(blob):
    """Run get_legacy_license_info with blob standing in for the on-disk license.

    The result is lru_cached, so the cache is dropped on both sides of the call to
    keep one case's answer from being handed to the next.
    """
    get_legacy_license_info.cache_clear()
    try:
        with patch("builtins.open", mock_open(read_data=blob)):
            return get_legacy_license_info()
    finally:
        get_legacy_license_info.cache_clear()


def _model_less_blob():
    """The X10 blob with its model field zeroed, giving a legacy license with no model.

    Legacy blobs carry neither a signature nor a checksum, so overwriting the field in
    place produces a blob that still parses. Offsets are the version byte followed by
    the 16-byte model field.
    """
    raw = bytearray(base64.b64decode(X10_BLOB))
    raw[1:17] = b"\x00" * 16
    return base64.b64encode(bytes(raw)).decode()


# A freenas-model blob is not a license: the system reads as unlicensed rather than
# picking up the flags the translation would otherwise inject into it.
def test__get_legacy_license_info_drops_freenas_model():
    assert _legacy_info_for(FREENAS_MINI_BLOB) is None


def test__get_legacy_license_info_keeps_enterprise_model():
    info = _legacy_info_for(X10_BLOB)
    assert info is not None
    assert info.model == "X10"


# Only a freenas-prefixed model is rejected; a blob with no model at all is still a license
# and gets the same unconditional injection set as any other.
def test__get_legacy_license_info_keeps_model_less_blob():
    blob = _model_less_blob()
    assert parse_legacy_license(blob).model is None

    info = _legacy_info_for(blob)
    assert info is not None
    assert info.model is None
    assert info.has_feature(LicenseFeature.SMB_VEEAM)
    assert info.has_feature(LicenseFeature.SMB_FASTPATH)


def test__legacy_injection_set_is_pinned():
    assert _LEGACY_INJECT == [
        "APPS",
        "AUTOTUNE",
        "CATALOG_ENTERPRISE_TRAIN",
        "CONTAINERS",
        "DIRECTORY_SERVICES_AUTH",
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
    ]


# The point of the injection: a flag put on the license has to survive the engine, or the
# upgrade path it exists to protect is broken. Every legacy blob in the field goes through
# this translation, so this is the entitlement floor for the whole installed base.
def test__legacy_license_is_entitled_to_every_injected_feature():
    facts = EntitlementFacts(hardware_class=HardwareClass.TRUENAS_HW, license=parse_legacy_license(X10_BLOB))
    denied = [f.value for f in _LEGACY_INJECT_SET if f in POLICY and not check_entitlement(f, facts).entitled]
    assert denied == []


def test__injected_features_without_a_policy_rule_are_pinned():
    # The check above can only speak for keys the engine has a rule for. Naming the rest
    # means a feature gaining a POLICY entry gets asserted rather than silently skipped.
    assert {f for f in _LEGACY_INJECT_SET if f not in POLICY} == {LicenseFeature.AUTOTUNE}


# The feature bits the legacy format could carry, in the modern vocabulary.
_LEGACY_BITMASK_FEATURES = {str(FEATURE_NAME_MAP.get(f.name.upper(), f.name.upper())) for f in Features}


def test__legacy_bitmask_is_the_other_route_onto_a_legacy_license():
    # SED, FIBRECHANNEL and DEDUP are not injected, so a legacy holder only has them if the
    # blob's own bits carry them. Dropping one of these from the bitmask translation would
    # revoke it from every legacy licensee that bought it.
    assert _LEGACY_BITMASK_FEATURES - {f.value for f in _LEGACY_INJECT_SET} == {"SED", "FIBRECHANNEL", "DEDUP"}


def test__legacy_fibrechannel_bit_is_observable_end_to_end():
    # The positive control for the route above. The CE side is where a key is visible:
    # FIBRECHANNEL's vector grants CE+K and denies CE+L, whereas appliance hardware is
    # granted by any license at all and so cannot tell the two apart.
    with_bit = parse_legacy_license(H10_HA_BLOB)
    without_bit = parse_legacy_license(X10_BLOB)
    assert with_bit.has_feature(LicenseFeature.FIBRECHANNEL)
    assert not without_bit.has_feature(LicenseFeature.FIBRECHANNEL)

    def entitled(info):
        facts = EntitlementFacts(hardware_class=HardwareClass.GENERIC, license=info)
        return check_entitlement(LicenseFeature.FIBRECHANNEL, facts).entitled

    assert entitled(with_bit) is True
    assert entitled(without_bit) is False


def test__zfstier_is_denied_on_every_legacy_license():
    # No legacy blob can carry ZFSTIER; pinned so adding a route is a decision, not an accident.
    assert LicenseFeature.ZFSTIER not in _LEGACY_INJECT_SET
    assert LicenseFeature.ZFSTIER.value not in _LEGACY_BITMASK_FEATURES

    info = parse_legacy_license(H10_HA_BLOB)
    assert not info.has_feature(LicenseFeature.ZFSTIER)
    facts = EntitlementFacts(hardware_class=HardwareClass.TRUENAS_HW, license=info)
    assert check_entitlement(LicenseFeature.ZFSTIER, facts).entitled is False
