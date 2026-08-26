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
            start_date=start,
            expires_at=end if name == "SUPPORT" else None,
            source="enterprise",
            type=support_type if name == "SUPPORT" else None,
        )
        for name in names
    }


# The production injection set, which fires for every legacy blob that parses, ordered the
# way parse_legacy_license appends it: by LicenseFeature declaration, after the license's
# own bits. Derived rather than copied, so the expectations below cannot drift from the set
# they describe. test__legacy_injection_set_is_pinned is what keeps that from making the
# comparison vacuous.
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
        # SUPPORT, plus the all-legacy and enterprise-only injected flags.
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
        # freenascertified license (freenas-prefixed model). parse_legacy_license still
        # translates it in full -- the model is only rejected a layer up, in
        # get_legacy_license_info. FREENASCERTIFIED is not a support tier, so the
        # injected SUPPORT flag is stamped BRONZE.
        (
            FREENAS_MINI_BLOB,
            LicenseInfo(
                id="legacy_TEST-000001",
                type=LicenseType.ENTERPRISE_SINGLE,
                model="FREENAS-MINI",
                support_expires_at=date(2026, 4, 30),
                features=_features(_LEGACY_INJECT, support_type="BRONZE"),
                serials=("TEST-000001",),
                enclosures={},
                contract_type="FREENASCERTIFIED",
            ),
        ),
    ],
)
def test__parse_legacy_license(text, result):
    assert parse_legacy_license(text) == result


# A legacy blob carries no per-feature dates, so the only date the translation can honestly
# put on a feature is the support contract's end, on SUPPORT. Stamping it onto the rest would
# claim an expiry that was never sold, and nothing gates on a feature's date, so the only way
# this stays true is by being asserted.
@pytest.mark.parametrize("text", [H10_HA_BLOB, X10_BLOB, FREENAS_MINI_BLOB])
def test__legacy_expiry_lands_on_support_alone(text):
    info = parse_legacy_license(text)

    assert info.features["SUPPORT"].expires_at == date(2026, 4, 30)
    assert [name for name, f in info.features.items() if f.expires_at is not None] == ["SUPPORT"]
    assert all(f.start_date == date(2026, 4, 8) for f in info.features.values())


# A legacy blob carries no license type of its own: the second (HA) serial is the only
# thing that distinguishes an HA license from a single-head one, and it is what the
# translation turns into LicenseType.
@pytest.mark.parametrize(
    "text,type_",
    [
        # H10 with system_serial_ha = TEST-000002.
        (
            H10_HA_BLOB,
            LicenseType.ENTERPRISE_HA,
        ),
        # X10 with an empty system_serial_ha field.
        (X10_BLOB, LicenseType.ENTERPRISE_SINGLE),
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
    [X10_BLOB, FREENAS_MINI_BLOB],
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


# The positive control for the drop above, so it cannot pass because the stubbed read
# or the parse failed for some reason unrelated to the model.
def test__get_legacy_license_info_keeps_enterprise_model():
    info = _legacy_info_for(X10_BLOB)
    assert info is not None
    assert info.model == "X10"


# Only a freenas-prefixed model is rejected; a blob with no model at all is still a
# license. It is also the only holder that the merged injection set widens, so the two
# flags that widening actually grants are pinned here rather than left to drift.
def test__get_legacy_license_info_keeps_model_less_blob():
    blob = _model_less_blob()
    assert parse_legacy_license(blob).model is None

    info = _legacy_info_for(blob)
    assert info is not None
    assert info.model is None
    assert info.has_feature(LicenseFeature.SMB_VEEAM)
    assert info.has_feature(LicenseFeature.SMB_FASTPATH)


# Deriving _LEGACY_INJECT from the production set keeps the expectations above from drifting,
# but on its own it also makes them tautological. This is the fence that recovers them: both
# membership and the order flags land in are written out once. Widening the set hands a
# feature to the entire legacy installed base, so it has to be written down here too.
def test__legacy_injection_set_is_pinned():
    assert _LEGACY_INJECT == [
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


# The five feature bits the legacy format could carry, in the modern vocabulary.
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


@pytest.mark.parametrize("hardware_class", [HardwareClass.TRUENAS_HW, HardwareClass.MINI, HardwareClass.GENERIC])
@pytest.mark.parametrize("blob", [H10_HA_BLOB, X10_BLOB, FREENAS_MINI_BLOB])
def test__zfstier_is_denied_on_every_legacy_license(blob, hardware_class):
    # ZFSTIER has neither a legacy feature bit nor an injection entry, so no legacy blob can
    # put the key on the license, and its vector grants only where the key is. Legacy holders
    # are therefore permanently denied it -- a deliberate outcome, pinned so that adding a
    # route in either direction is a decision rather than an accident.
    assert LicenseFeature.ZFSTIER not in _LEGACY_INJECT_SET
    assert LicenseFeature.ZFSTIER.value not in _LEGACY_BITMASK_FEATURES

    info = parse_legacy_license(blob)
    assert not info.has_feature(LicenseFeature.ZFSTIER)
    facts = EntitlementFacts(hardware_class=hardware_class, license=info)
    assert check_entitlement(LicenseFeature.ZFSTIER, facts).entitled is False
