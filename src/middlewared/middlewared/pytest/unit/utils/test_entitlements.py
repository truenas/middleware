import typing

import pytest
from truenas_pylicensed import LicenseType
from truenas_pylicensed.features import FEATURE_TIERS, LicenseFeature, SupportTier

from middlewared.api.v26_0_0.truenas import EntitlementEntry
from middlewared.pytest.unit.entitlements import facts_for_column, make_facts, make_license
from middlewared.utils.license import LicenseInfo
from middlewared.utils.entitlements import (
    COLUMNS,
    FEATURE_DISPLAY_NAMES,
    POLICY,
    TARGET_VECTORS,
    DerivedEntitlement,
    HardwareClass,
    LegacyRule,
    LicenseTypeRule,
    Reason,
    TierRule,
    Vector,
    check_entitlement,
)
from middlewared.utils.entitlements.engine import _MESSAGES


# (a) The product feature matrix, written out. Every row is a decision about who gets what,
# so a cell that changes has to change here too rather than riding along with a refactor.
# It is also what makes the single representative-per-shape table below safe: the features
# that share a shape are pinned here instead of being swept there.
def test_target_vectors_match_the_product_matrix():
    assert TARGET_VECTORS == {
        LicenseFeature.APPS: Vector(ce=1, hw=1, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.AUTOTUNE: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=0),
        LicenseFeature.CATALOG_ENTERPRISE_TRAIN: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=0),
        LicenseFeature.CONTAINERS: Vector(ce=1, hw=1, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.DEDUP: Vector(ce=1, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.DIRECTORY_SERVICES: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.FIBRECHANNEL: Vector(ce=0, hw=0, hw_l=1, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.KMIP: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.MISSION_CRITICAL: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.NETWORK_FEC: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.NFS_SNAPSHOT: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.NVMEOF_SPDK: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.RDMA: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.SED: Vector(ce=0, hw=1, hw_l=1, hw_k=1, ce_l=1, ce_k=1),
        LicenseFeature.SMB_FASTPATH: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.SMB_VEEAM: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.STIG: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.SUPPORT: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.TRUESEARCH: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.VMS: Vector(ce=1, hw=1, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.WEBSHARE: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.ZFSTIER: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
    }


# (b) Live POLICY shape: which keys have a rule, and of which kind.
def test_live_policy_shape():
    assert set(POLICY) == {
        LicenseFeature.CATALOG_ENTERPRISE_TRAIN,
        LicenseFeature.DEDUP,
        LicenseFeature.DIRECTORY_SERVICES,
        LicenseFeature.FIBRECHANNEL,
        LicenseFeature.KMIP,
        LicenseFeature.MISSION_CRITICAL,
        LicenseFeature.ZFSTIER,
        LicenseFeature.APPS,
        LicenseFeature.CONTAINERS,
        LicenseFeature.VMS,
        LicenseFeature.WEBSHARE,
        LicenseFeature.SED,
        LicenseFeature.SMB_FASTPATH,
        LicenseFeature.SMB_VEEAM,
        LicenseFeature.STIG,
        LicenseFeature.SUPPORT,
        LicenseFeature.TRUESEARCH,
        LicenseFeature.NFS_SNAPSHOT,
        LicenseFeature.NVMEOF_SPDK,
        LicenseFeature.NETWORK_FEC,
        LicenseFeature.RDMA,
        DerivedEntitlement.HA,
        DerivedEntitlement.PROACTIVE_SUPPORT,
    }
    assert isinstance(POLICY[DerivedEntitlement.HA], LicenseTypeRule)
    assert isinstance(POLICY[DerivedEntitlement.PROACTIVE_SUPPORT], TierRule)
    # Every license feature the policy rules on is bound to a matrix Vector.
    for key in set(POLICY) - set(DerivedEntitlement):
        assert isinstance(POLICY[key], Vector), key
    # The LegacyRule kind is retained in the engine for future use but no live entry uses it.
    assert not [rule for rule in POLICY.values() if isinstance(rule, LegacyRule)]


# (c) Completeness (D-SYNC): adding a flag must not silently skip a site.
def test_target_vectors_cover_every_license_feature():
    assert set(LicenseFeature) == set(TARGET_VECTORS)


def test_policy_keys_are_known_vocabulary():
    assert set(POLICY) <= set(LicenseFeature) | set(DerivedEntitlement)
    # And the other direction, so a new DerivedEntitlement member cannot be added
    # without a rule and then quietly raise ValueError at its first call site.
    assert set(DerivedEntitlement) <= set(POLICY)


def test_policy_keys_have_display_names():
    assert set(POLICY) <= set(FEATURE_DISPLAY_NAMES)


def test_every_reason_has_a_message_template():
    # `_format_message` looks the reason up in this map, so a member added without an entry
    # would only surface at the first call site that produced it.
    assert set(Reason) == set(_MESSAGES)


def test_api_reason_literal_matches_engine_reason():
    # The import contract keeps modules under middlewared.api.v* away from the engine, so the
    # public reason vocabulary has to be spelled out again there. This is what keeps the copy
    # honest.
    literal = EntitlementEntry.model_fields["reason"].annotation
    assert set(typing.get_args(literal)) == {r.value for r in Reason}


def test_declared_tiers_cover_tier_rules():
    for rule in POLICY.values():
        if isinstance(rule, TierRule):
            assert rule.feature in FEATURE_TIERS
            assert rule.allowed_tiers <= set(FEATURE_TIERS[rule.feature])


@pytest.mark.parametrize(
    "vector",
    [
        Vector(ce=1, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        Vector(ce=0, hw=1, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        Vector(ce=0, hw=0, hw_l=1, hw_k=1, ce_l=0, ce_k=1),  # the shape the product matrix used to carry
        Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=1, ce_k=1),
    ],
)
def test_tier_rule_rejects_a_cell_outside_the_key_columns(vector):
    with pytest.raises(ValueError, match="read off a feature key"):
        TierRule(feature=LicenseFeature.SUPPORT, allowed_tiers=frozenset({SupportTier.GOLD}), vector=vector)


def test_columns_match_vector_fields():
    assert Vector._fields == tuple(c.lower().replace("+", "_") for c in COLUMNS)


def _license_for(feature: str, state: str) -> LicenseInfo | None:
    if state == "none":
        return None
    if state == "key":
        return make_license(feature_names=(feature,))
    return make_license(feature_names=())  # "nokey": licensed, without this feature's key


# (d) Vector resolution, once per distinct live vector shape.
#
# The features sharing a shape are pinned by the matrix test above, so sweeping them here
# would only run the same six cells again. The engine reads `hardware_class` solely through
# `.is_appliance`, so TRUENAS_HW and GENERIC are the two sides it can tell apart -- the one
# MINI row at the end is what pins Minis onto the CE side rather than their own.
#
# Between them these reach all six columns and all four reasons a vector can produce.
VECTOR_TABLE = [
    # APPS/CONTAINERS/VMS (1,1,0,1,0,1): granted unlicensed on either side, and a license
    # without the key revokes it.
    (LicenseFeature.APPS, HardwareClass.TRUENAS_HW, "none", True, "ENTITLED", "HW"),
    (LicenseFeature.APPS, HardwareClass.TRUENAS_HW, "nokey", False, "KEY_MISSING", "HW+L"),
    (LicenseFeature.APPS, HardwareClass.TRUENAS_HW, "key", True, "ENTITLED", "HW+K"),
    (LicenseFeature.APPS, HardwareClass.GENERIC, "none", True, "ENTITLED", "CE"),
    (LicenseFeature.APPS, HardwareClass.GENERIC, "nokey", False, "KEY_MISSING", "CE+L"),
    (LicenseFeature.APPS, HardwareClass.GENERIC, "key", True, "ENTITLED", "CE+K"),
    # CATALOG_ENTERPRISE_TRAIN (0,0,0,1,0,0): the only live shape whose CE key cell is 0, so
    # it is the only one where a key on the community side still denies.
    (LicenseFeature.CATALOG_ENTERPRISE_TRAIN, HardwareClass.TRUENAS_HW, "none", False, "NO_LICENSE", "HW"),
    (LicenseFeature.CATALOG_ENTERPRISE_TRAIN, HardwareClass.TRUENAS_HW, "nokey", False, "KEY_MISSING", "HW+L"),
    (LicenseFeature.CATALOG_ENTERPRISE_TRAIN, HardwareClass.TRUENAS_HW, "key", True, "ENTITLED", "HW+K"),
    (LicenseFeature.CATALOG_ENTERPRISE_TRAIN, HardwareClass.GENERIC, "none", False, "WRONG_HARDWARE", "CE"),
    (LicenseFeature.CATALOG_ENTERPRISE_TRAIN, HardwareClass.GENERIC, "nokey", False, "WRONG_HARDWARE", "CE+L"),
    (LicenseFeature.CATALOG_ENTERPRISE_TRAIN, HardwareClass.GENERIC, "key", False, "WRONG_HARDWARE", "CE+K"),
    # DEDUP (1,0,0,1,0,1): free on the community side, keyed on appliance hardware.
    (LicenseFeature.DEDUP, HardwareClass.TRUENAS_HW, "none", False, "NO_LICENSE", "HW"),
    (LicenseFeature.DEDUP, HardwareClass.TRUENAS_HW, "nokey", False, "KEY_MISSING", "HW+L"),
    (LicenseFeature.DEDUP, HardwareClass.TRUENAS_HW, "key", True, "ENTITLED", "HW+K"),
    (LicenseFeature.DEDUP, HardwareClass.GENERIC, "none", True, "ENTITLED", "CE"),
    (LicenseFeature.DEDUP, HardwareClass.GENERIC, "nokey", False, "KEY_MISSING", "CE+L"),
    (LicenseFeature.DEDUP, HardwareClass.GENERIC, "key", True, "ENTITLED", "CE+K"),
    # ZFSTIER, and the thirteen other features sharing (0,0,0,1,0,1): key-only on either side.
    (LicenseFeature.ZFSTIER, HardwareClass.TRUENAS_HW, "none", False, "NO_LICENSE", "HW"),
    (LicenseFeature.ZFSTIER, HardwareClass.TRUENAS_HW, "nokey", False, "KEY_MISSING", "HW+L"),
    (LicenseFeature.ZFSTIER, HardwareClass.TRUENAS_HW, "key", True, "ENTITLED", "HW+K"),
    (LicenseFeature.ZFSTIER, HardwareClass.GENERIC, "none", False, "NO_LICENSE", "CE"),
    (LicenseFeature.ZFSTIER, HardwareClass.GENERIC, "nokey", False, "KEY_MISSING", "CE+L"),
    (LicenseFeature.ZFSTIER, HardwareClass.GENERIC, "key", True, "ENTITLED", "CE+K"),
    # FIBRECHANNEL (0,0,1,1,0,1): any license grants it on appliance hardware; the community
    # side needs the key.
    (LicenseFeature.FIBRECHANNEL, HardwareClass.TRUENAS_HW, "none", False, "NO_LICENSE", "HW"),
    (LicenseFeature.FIBRECHANNEL, HardwareClass.TRUENAS_HW, "nokey", True, "ENTITLED", "HW+L"),
    (LicenseFeature.FIBRECHANNEL, HardwareClass.TRUENAS_HW, "key", True, "ENTITLED", "HW+K"),
    (LicenseFeature.FIBRECHANNEL, HardwareClass.GENERIC, "none", False, "NO_LICENSE", "CE"),
    (LicenseFeature.FIBRECHANNEL, HardwareClass.GENERIC, "nokey", False, "KEY_MISSING", "CE+L"),
    (LicenseFeature.FIBRECHANNEL, HardwareClass.GENERIC, "key", True, "ENTITLED", "CE+K"),
    # SED (0,1,1,1,1,1): denied only on an unlicensed community system.
    (LicenseFeature.SED, HardwareClass.TRUENAS_HW, "none", True, "ENTITLED", "HW"),
    (LicenseFeature.SED, HardwareClass.TRUENAS_HW, "nokey", True, "ENTITLED", "HW+L"),
    (LicenseFeature.SED, HardwareClass.TRUENAS_HW, "key", True, "ENTITLED", "HW+K"),
    (LicenseFeature.SED, HardwareClass.GENERIC, "none", False, "NO_LICENSE", "CE"),
    (LicenseFeature.SED, HardwareClass.GENERIC, "nokey", True, "ENTITLED", "CE+L"),
    (LicenseFeature.SED, HardwareClass.GENERIC, "key", True, "ENTITLED", "CE+K"),
    # A Mini is iX-built hardware that reads the CE half of every row, so unlicensed DEDUP is
    # granted here and denied on the appliance row above.
    (LicenseFeature.DEDUP, HardwareClass.MINI, "none", True, "ENTITLED", "CE"),
]


@pytest.mark.parametrize("feature,hardware_class,state,entitled,reason,column", VECTOR_TABLE)
def test_vector_behavior(feature, hardware_class, state, entitled, reason, column):
    facts = make_facts(hardware_class=hardware_class, license=_license_for(feature, state))
    entitlement = check_entitlement(feature, facts)
    assert entitlement.entitled is entitled
    assert entitlement.reason == reason
    assert entitlement.column == column


# (e) Where a denial's wording comes from. A feature may register bespoke wording that has to
# win over the generic template on every reason it registers, and a feature with no display
# name has to fall back to its raw key rather than emitting an empty phrase.
_CE_KEY_DROPPED = Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=0)

MESSAGE_TABLE = [
    # An override replaces the generic template on a live denial.
    (LicenseFeature.NVMEOF_SPDK, "HW+L", None, "SPDK is limited to enterprise licensed systems only."),
    # ... and holds on WRONG_HARDWARE too, which no live vector with an override can reach.
    (
        LicenseFeature.SMB_VEEAM,
        "CE+K",
        _CE_KEY_DROPPED,
        "Veeam repository shares require a TrueNAS enterprise license.",
    ),
    # No override: the generic template is filled from the display name, not the key.
    (LicenseFeature.DEDUP, "HW+L", None, "This system's license does not include the ZFS deduplication feature."),
    # No display name either, so the raw key is what the template gets.
    (
        "SYNTHETIC_UNNAMED",
        "HW",
        Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        "This system is not licensed to use the SYNTHETIC_UNNAMED feature.",
    ),
]


@pytest.mark.parametrize("feature,column,vector,message", MESSAGE_TABLE)
def test_message_source(feature, column, vector, message):
    policy = None if vector is None else {feature: vector}
    entitlement = check_entitlement(feature, facts_for_column(feature, column), policy=policy)
    assert entitlement.entitled is False
    assert entitlement.message == message


# (f) Unknown feature.
def test_unknown_feature_raises():
    with pytest.raises(ValueError):
        check_entitlement("NOPE", make_facts(hardware_class=HardwareClass.GENERIC))


def _proactive_support_license(state: str, support_type: str | None) -> LicenseInfo | None:
    if state == "none":
        return None
    if state == "key":
        return make_license(feature_names=("SUPPORT",), support_type=support_type)
    return make_license(feature_names=())  # "nokey": licensed, without the SUPPORT key


PROACTIVE_SUPPORT_NO_LICENSE = "This system is not licensed to use the proactive support feature."
PROACTIVE_SUPPORT_KEY_MISSING = "This system's license does not include the proactive support feature."
PROACTIVE_SUPPORT_TIER = "This system's support tier does not include the proactive support feature."

# (g) PROACTIVE_SUPPORT: the live TierRule, which is the only rule kind that reads a
# qualifier off a feature key other than its own policy key. The messages are asserted
# because that split is invisible to mypy -- both are `str` -- and conflating them would
# emit "the support feature" here, which is a different entitlement.
TIER_TABLE = [
    (HardwareClass.TRUENAS_HW, "none", None, False, "NO_LICENSE", "HW", PROACTIVE_SUPPORT_NO_LICENSE),
    (HardwareClass.TRUENAS_HW, "nokey", None, False, "KEY_MISSING", "HW+L", PROACTIVE_SUPPORT_KEY_MISSING),
    (HardwareClass.TRUENAS_HW, "key", "GOLD", True, "ENTITLED", "HW+K", ""),
    (HardwareClass.TRUENAS_HW, "key", "SILVER", True, "ENTITLED", "HW+K", ""),
    (HardwareClass.TRUENAS_HW, "key", "SILVERINTERNATIONAL", True, "ENTITLED", "HW+K", ""),
    # The tier is upper-cased before it is matched.
    (HardwareClass.TRUENAS_HW, "key", "gold", True, "ENTITLED", "HW+K", ""),
    (HardwareClass.TRUENAS_HW, "key", "BRONZE", False, "TIER_INSUFFICIENT", "HW+K", PROACTIVE_SUPPORT_TIER),
    # The SUPPORT key is present but carries no tier at all.
    (HardwareClass.TRUENAS_HW, "key", None, False, "TIER_INSUFFICIENT", "HW+K", PROACTIVE_SUPPORT_TIER),
    (HardwareClass.GENERIC, "none", None, False, "NO_LICENSE", "CE", PROACTIVE_SUPPORT_NO_LICENSE),
    (HardwareClass.GENERIC, "nokey", None, False, "KEY_MISSING", "CE+L", PROACTIVE_SUPPORT_KEY_MISSING),
    (HardwareClass.GENERIC, "key", "GOLD", True, "ENTITLED", "CE+K", ""),
]


@pytest.mark.parametrize("hardware_class,state,support_type,entitled,reason,column,message", TIER_TABLE)
def test_tier_rule_behavior(hardware_class, state, support_type, entitled, reason, column, message):
    facts = make_facts(hardware_class=hardware_class, license=_proactive_support_license(state, support_type))
    entitlement = check_entitlement(DerivedEntitlement.PROACTIVE_SUPPORT, facts)
    assert entitlement.entitled is entitled
    assert entitlement.reason == reason
    # The tier is a qualifier on the key columns, so the SUPPORT key -- not the policy key,
    # which no license carries -- is what resolves the column.
    assert entitlement.column == column
    assert entitlement.message == message


# (h) HA: the live LicenseTypeRule. The license type decides outright and the hardware class
# only names the column, so an ENTERPRISE_HA license grants it everywhere and an
# ENTERPRISE_SINGLE one grants it nowhere. These fail if HA is ever given a matrix Vector,
# since a Vector would make the answer depend on the hardware side and on a LicenseFeature.HA
# key that does not exist.
LICENSE_TYPE_TABLE = [
    (HardwareClass.TRUENAS_HW, LicenseType.ENTERPRISE_HA, True, "ENTITLED", "HW+L"),
    (HardwareClass.TRUENAS_HW, LicenseType.ENTERPRISE_SINGLE, False, "WRONG_LICENSE_TYPE", "HW+L"),
    (HardwareClass.TRUENAS_HW, None, False, "NO_LICENSE", "HW"),
    (HardwareClass.GENERIC, LicenseType.ENTERPRISE_HA, True, "ENTITLED", "CE+L"),
    (HardwareClass.MINI, LicenseType.ENTERPRISE_HA, True, "ENTITLED", "CE+L"),
]


@pytest.mark.parametrize("hardware_class,type_,entitled,reason,column", LICENSE_TYPE_TABLE)
def test_license_type_rule_behavior(hardware_class, type_, entitled, reason, column):
    license = None if type_ is None else make_license(type_=type_)
    entitlement = check_entitlement(DerivedEntitlement.HA, make_facts(hardware_class=hardware_class, license=license))
    assert entitlement.entitled is entitled
    assert entitlement.reason == reason
    assert entitlement.column == column
