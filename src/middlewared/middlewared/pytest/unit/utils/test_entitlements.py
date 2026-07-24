import typing
from datetime import date, timedelta

import pytest
from truenas_pylicensed import LicenseType
from truenas_pylicensed.features import FEATURE_TIERS, LicenseFeature

from middlewared.api.v26_0_0.system_product import SystemFeatureEnabledArgs
from middlewared.plugins.truenas.license_utils import FeatureInfo, LicenseInfo
from middlewared.utils.entitlements import (
    COLUMNS,
    FEATURE_DISPLAY_NAMES,
    FEATURE_MESSAGES,
    POLICY,
    TARGET_VECTORS,
    DerivedEntitlement,
    EntitlementFacts,
    HardwareClass,
    LegacyRule,
    LicenseTypeRule,
    Reason,
    TierRule,
    Vector,
    check,
)


def make_license(
    *,
    feature_names: tuple[str, ...] = (),
    type_: LicenseType = LicenseType.ENTERPRISE_SINGLE,
    model: str | None = "H10",
    expires_at: date | None = None,
    support_type: str | None = None,
) -> LicenseInfo:
    features = [
        FeatureInfo(
            name=name,
            start_date=None,
            expires_at=expires_at,
            source="enterprise",
            type=support_type if name == "SUPPORT" else None,
        )
        for name in feature_names
    ]
    return LicenseInfo(
        id="test-license",
        type=type_,
        model=model,
        expires_at=expires_at,
        features=features,
        serials=["TEST-000001"],
        enclosures={},
        contract_type=support_type,
    )


def make_facts(
    *,
    hardware_class: HardwareClass,
    is_ha_capable: bool = False,
    license: LicenseInfo | None = None,
) -> EntitlementFacts:
    return EntitlementFacts(
        hardware_class=hardware_class,
        is_ha_capable=is_ha_capable,
        license=license,
    )


def facts_for_column(feature: str, column: str, *, is_ha_capable: bool = False) -> EntitlementFacts:
    hardware_class = HardwareClass.TRUENAS_HW if column in ("HW", "HW+L", "HW+K") else HardwareClass.GENERIC
    if column in ("CE", "HW"):
        license = None
    elif column in ("HW+K", "CE+K"):
        license = make_license(feature_names=(feature,))
    else:  # HW+L / CE+L: licensed, but without this feature's key
        license = make_license(feature_names=())
    return make_facts(hardware_class=hardware_class, is_ha_capable=is_ha_capable, license=license)


# (a) Matrix fixture: every feature vector against every column resolves to the matrix cell.
@pytest.mark.parametrize("feature,column", [(f, c) for f in TARGET_VECTORS for c in COLUMNS])
def test_matrix_fixture(feature, column):
    cell = TARGET_VECTORS[feature][COLUMNS.index(column)]
    entitlement = check(feature, facts_for_column(feature, column), policy=TARGET_VECTORS)
    assert entitlement.entitled == bool(cell)
    assert entitlement.column == column


# (b) Live POLICY shape: one entry per rule kind currently in active use.
def test_live_policy_shape():
    assert set(POLICY) == {
        LicenseFeature.DEDUP,
        LicenseFeature.ZFSTIER,
        LicenseFeature.SED,
        LicenseFeature.NVMEOF_SPDK,
        DerivedEntitlement.HA,
        DerivedEntitlement.PROACTIVE_SUPPORT,
    }
    assert isinstance(POLICY[LicenseFeature.DEDUP], Vector)
    assert isinstance(POLICY[LicenseFeature.ZFSTIER], Vector)
    assert isinstance(POLICY[LicenseFeature.SED], LegacyRule)
    assert isinstance(POLICY[LicenseFeature.NVMEOF_SPDK], LegacyRule)
    assert isinstance(POLICY[DerivedEntitlement.HA], LicenseTypeRule)
    assert isinstance(POLICY[DerivedEntitlement.PROACTIVE_SUPPORT], TierRule)


# (c) Completeness (D-SYNC): adding a flag must not silently skip a site.
def test_target_vectors_cover_every_license_feature():
    assert set(LicenseFeature) == set(TARGET_VECTORS)


def test_policy_keys_are_known_vocabulary():
    assert set(POLICY) <= set(LicenseFeature) | set(DerivedEntitlement)


def test_policy_keys_have_display_names():
    assert set(POLICY) <= set(FEATURE_DISPLAY_NAMES)


def test_api_feature_literal_matches_license_features():
    literal = SystemFeatureEnabledArgs.model_fields["feature"].annotation
    assert set(typing.get_args(literal)) == {f.value for f in LicenseFeature}


def test_declared_tiers_cover_tier_rules():
    for rule in POLICY.values():
        if isinstance(rule, TierRule):
            assert rule.feature in FEATURE_TIERS
            assert rule.allowed_tiers <= set(FEATURE_TIERS[rule.feature])


def test_columns_match_vector_fields():
    assert Vector._fields == tuple(c.lower().replace("+", "_") for c in COLUMNS)


def _license_for(feature: str, state: str) -> LicenseInfo | None:
    if state == "none":
        return None
    if state == "key":
        return make_license(feature_names=(feature,))
    return make_license(feature_names=())  # "nokey": licensed, without this feature's key


# DEDUP is a live matrix Vector.
DEDUP_TABLE = [
    (HardwareClass.TRUENAS_HW, "none", False, "NO_LICENSE", "HW"),
    (HardwareClass.TRUENAS_HW, "nokey", False, "KEY_MISSING", "HW+L"),
    (HardwareClass.TRUENAS_HW, "key", True, "ENTITLED", "HW+K"),
    (HardwareClass.MINI, "none", True, "ENTITLED", "CE"),
    (HardwareClass.MINI, "nokey", False, "KEY_MISSING", "CE+L"),
    (HardwareClass.MINI, "key", True, "ENTITLED", "CE+K"),
    (HardwareClass.GENERIC, "none", True, "ENTITLED", "CE"),
    (HardwareClass.GENERIC, "nokey", False, "KEY_MISSING", "CE+L"),
    (HardwareClass.GENERIC, "key", True, "ENTITLED", "CE+K"),
]


@pytest.mark.parametrize("hardware_class,state,entitled,reason,column", DEDUP_TABLE)
def test_dedup_vector_behavior(hardware_class, state, entitled, reason, column):
    facts = make_facts(hardware_class=hardware_class, license=_license_for(LicenseFeature.DEDUP, state))
    entitlement = check(LicenseFeature.DEDUP, facts)
    assert entitlement.entitled is entitled
    assert entitlement.reason == reason
    assert entitlement.column == column


def test_dedup_no_license_message_uses_display_name():
    entitlement = check(LicenseFeature.DEDUP, make_facts(hardware_class=HardwareClass.TRUENAS_HW))
    assert entitlement.message == "This system is not licensed to use the ZFS deduplication feature."


def test_dedup_key_missing_message_uses_display_name():
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license())
    entitlement = check(LicenseFeature.DEDUP, facts)
    assert entitlement.message == "This system's license does not include the ZFS deduplication feature."


# ZFSTIER is a live matrix Vector (0,0,0,1,0,1): key-only on either hardware side.
ZFSTIER_TABLE = [
    (HardwareClass.TRUENAS_HW, "none", False, "NO_LICENSE", "HW"),
    (HardwareClass.TRUENAS_HW, "nokey", False, "KEY_MISSING", "HW+L"),
    (HardwareClass.TRUENAS_HW, "key", True, "ENTITLED", "HW+K"),
    (HardwareClass.MINI, "none", False, "NO_LICENSE", "CE"),
    (HardwareClass.MINI, "nokey", False, "KEY_MISSING", "CE+L"),
    (HardwareClass.MINI, "key", True, "ENTITLED", "CE+K"),
    (HardwareClass.GENERIC, "none", False, "NO_LICENSE", "CE"),
    (HardwareClass.GENERIC, "nokey", False, "KEY_MISSING", "CE+L"),
    (HardwareClass.GENERIC, "key", True, "ENTITLED", "CE+K"),
]


@pytest.mark.parametrize("hardware_class,state,entitled,reason,column", ZFSTIER_TABLE)
def test_zfstier_vector_behavior(hardware_class, state, entitled, reason, column):
    facts = make_facts(hardware_class=hardware_class, license=_license_for(LicenseFeature.ZFSTIER, state))
    entitlement = check(LicenseFeature.ZFSTIER, facts)
    assert entitlement.entitled is entitled
    assert entitlement.reason == reason
    assert entitlement.column == column


def test_legacy_nvmet_spdk_ha_capable_entitled_even_unlicensed():
    facts = make_facts(hardware_class=HardwareClass.GENERIC, is_ha_capable=True)
    assert check(LicenseFeature.NVMEOF_SPDK, facts).entitled is True


def test_legacy_nvmet_spdk_certified_model_entitled():
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(model="H10"))
    assert check(LicenseFeature.NVMEOF_SPDK, facts).entitled is True


def test_legacy_nvmet_spdk_freenas_model_blocked():
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(model="FREENAS-XYZ"))
    assert check(LicenseFeature.NVMEOF_SPDK, facts).entitled is False


def test_legacy_nvmet_spdk_model_none_blocked():
    facts = make_facts(hardware_class=HardwareClass.GENERIC, license=make_license(model=None))
    assert check(LicenseFeature.NVMEOF_SPDK, facts).entitled is False


def test_legacy_nvmet_spdk_unlicensed_no_license():
    facts = make_facts(hardware_class=HardwareClass.GENERIC)
    entitlement = check(LicenseFeature.NVMEOF_SPDK, facts)
    assert entitlement.entitled is False
    assert entitlement.reason == "NO_LICENSE"
    assert entitlement.message == "SPDK is limited to enterprise licensed systems only."


# NVMEOF_SPDK carries a bespoke message via FEATURE_MESSAGES so the wording
# survives an eventual flip from the LegacyRule to its matrix Vector.
def test_nvmeof_spdk_bespoke_message_registered():
    overrides = FEATURE_MESSAGES[LicenseFeature.NVMEOF_SPDK]
    for reason in (Reason.NO_LICENSE, Reason.KEY_MISSING, Reason.WRONG_HARDWARE):
        assert overrides[reason] == "SPDK is limited to enterprise licensed systems only."


def test_nvmeof_spdk_bespoke_message_survives_vector_flip():
    policy = {LicenseFeature.NVMEOF_SPDK: TARGET_VECTORS[LicenseFeature.NVMEOF_SPDK]}
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(feature_names=()))
    entitlement = check(LicenseFeature.NVMEOF_SPDK, facts, policy=policy)
    assert entitlement.reason == "KEY_MISSING"
    assert entitlement.message == "SPDK is limited to enterprise licensed systems only."


def test_legacy_sed_key_present_entitled():
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(feature_names=("SED",)))
    assert check(LicenseFeature.SED, facts).entitled is True


def test_legacy_sed_expired_key_still_entitled():
    # Membership-only: an expired SED feature still counts.
    facts = make_facts(
        hardware_class=HardwareClass.TRUENAS_HW,
        license=make_license(feature_names=("SED",), expires_at=date.today() - timedelta(days=1)),
    )
    assert check(LicenseFeature.SED, facts).entitled is True


def test_legacy_sed_no_key_key_missing():
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license())
    entitlement = check(LicenseFeature.SED, facts)
    assert entitlement.entitled is False
    assert entitlement.reason == "KEY_MISSING"


def test_legacy_sed_no_license():
    entitlement = check(LicenseFeature.SED, make_facts(hardware_class=HardwareClass.TRUENAS_HW))
    assert entitlement.entitled is False
    assert entitlement.reason == "NO_LICENSE"


# (d) Reason derivation from vectors.
def test_reason_fibrechannel_generic_no_license_is_no_license():
    entitlement = check(
        LicenseFeature.FIBRECHANNEL, facts_for_column(LicenseFeature.FIBRECHANNEL, "CE"), policy=TARGET_VECTORS
    )
    assert entitlement.entitled is False
    assert entitlement.reason == "NO_LICENSE"


def test_reason_fibrechannel_generic_keyless_license_is_key_missing():
    entitlement = check(
        LicenseFeature.FIBRECHANNEL, facts_for_column(LicenseFeature.FIBRECHANNEL, "CE+L"), policy=TARGET_VECTORS
    )
    assert entitlement.entitled is False
    assert entitlement.reason == "KEY_MISSING"


def test_reason_wrong_hardware():
    # Synthetic feature entitled only on HW+K -- a key on the CE side never grants it.
    policy = {"JBOF": Vector(0, 0, 0, 1, 0, 0)}
    entitlement = check("JBOF", facts_for_column("JBOF", "CE+K"), policy=policy)
    assert entitlement.entitled is False
    assert entitlement.reason == "WRONG_HARDWARE"


# (e) Revocation rule: a license lacking the key revokes a bare no-license grant.
def test_revocation_apps_generic_no_license_entitled():
    entitlement = check(LicenseFeature.APPS, facts_for_column(LicenseFeature.APPS, "CE"), policy=TARGET_VECTORS)
    assert entitlement.entitled is True
    assert entitlement.column == "CE"


def test_revocation_apps_generic_keyless_license_revoked():
    entitlement = check(LicenseFeature.APPS, facts_for_column(LicenseFeature.APPS, "CE+L"), policy=TARGET_VECTORS)
    assert entitlement.entitled is False
    assert entitlement.reason == "KEY_MISSING"
    assert entitlement.column == "CE+L"


# (f) Tier passthrough exposed on facts.
def test_tier_passthrough_exposed_on_facts():
    facts = make_facts(
        hardware_class=HardwareClass.TRUENAS_HW,
        license=make_license(feature_names=("SUPPORT",), support_type="GOLD"),
    )
    assert facts.license is not None
    support = next(f for f in facts.license.features if f.name == "SUPPORT")
    assert support.type == "GOLD"


# (g) HardwareClass.from_chassis.
@pytest.mark.parametrize(
    "chassis,expected",
    [
        ("TRUENAS-UNKNOWN", HardwareClass.GENERIC),
        ("TRUENAS-MINI-X+", HardwareClass.MINI),
        ("FREENAS-MINI-X", HardwareClass.MINI),
        ("TRUENAS-M50", HardwareClass.TRUENAS_HW),
        ("TRUENAS-F100", HardwareClass.TRUENAS_HW),
    ],
)
def test_hardware_class_from_chassis(chassis, expected):
    assert HardwareClass.from_chassis(chassis) is expected


# (h) Unknown feature.
def test_unknown_feature_raises():
    with pytest.raises(ValueError):
        check("NOPE", make_facts(hardware_class=HardwareClass.GENERIC))


# (i) PROACTIVE_SUPPORT: live TierRule over the SUPPORT tier qualifier.
@pytest.mark.parametrize(
    "support_type,entitled,reason",
    [
        ("GOLD", True, "ENTITLED"),
        ("SILVER", True, "ENTITLED"),
        ("SILVERINTERNATIONAL", True, "ENTITLED"),
        ("gold", True, "ENTITLED"),  # case-insensitive
        ("BRONZE", False, "TIER_INSUFFICIENT"),
        (None, False, "TIER_INSUFFICIENT"),  # SUPPORT key present but no tier
    ],
)
def test_proactive_support_tiers(support_type, entitled, reason):
    facts = make_facts(
        hardware_class=HardwareClass.TRUENAS_HW,
        license=make_license(feature_names=("SUPPORT",), support_type=support_type),
    )
    entitlement = check(DerivedEntitlement.PROACTIVE_SUPPORT, facts)
    assert entitlement.entitled is entitled
    assert entitlement.reason == reason


def test_proactive_support_key_absent_is_key_missing():
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(feature_names=()))
    entitlement = check(DerivedEntitlement.PROACTIVE_SUPPORT, facts)
    assert entitlement.entitled is False
    assert entitlement.reason == "KEY_MISSING"


def test_proactive_support_unlicensed_is_no_license():
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW)
    entitlement = check(DerivedEntitlement.PROACTIVE_SUPPORT, facts)
    assert entitlement.entitled is False
    assert entitlement.reason == "NO_LICENSE"


# (j) HA: live LicenseTypeRule over the license type.
def test_ha_entitled_for_enterprise_ha():
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(type_=LicenseType.ENTERPRISE_HA))
    assert check(DerivedEntitlement.HA, facts).entitled is True


def test_ha_wrong_type_for_enterprise_single():
    facts = make_facts(
        hardware_class=HardwareClass.TRUENAS_HW,
        license=make_license(type_=LicenseType.ENTERPRISE_SINGLE),
    )
    entitlement = check(DerivedEntitlement.HA, facts)
    assert entitlement.entitled is False
    assert entitlement.reason == "WRONG_LICENSE_TYPE"


def test_ha_unlicensed_is_no_license():
    entitlement = check(DerivedEntitlement.HA, make_facts(hardware_class=HardwareClass.TRUENAS_HW))
    assert entitlement.entitled is False
    assert entitlement.reason == "NO_LICENSE"
