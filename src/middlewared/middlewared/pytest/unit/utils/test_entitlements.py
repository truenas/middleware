import typing
from datetime import date, timedelta

import pytest
from truenas_pylicensed import LicenseType
from truenas_pylicensed.features import FEATURE_TIERS, LicenseFeature

from middlewared.api.v26_0_0.system_product import SystemFeatureEnabledArgs
from middlewared.utils.license import FeatureInfo, LicenseInfo
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
    check_entitlement,
)


def make_license(
    *,
    feature_names: tuple[str, ...] = (),
    type_: LicenseType = LicenseType.ENTERPRISE_SINGLE,
    model: str | None = "H10",
    expires_at: date | None = None,
    support_type: str | None = None,
) -> LicenseInfo:
    features = {
        name: FeatureInfo(
            name=name,
            start_date=None,
            expires_at=expires_at,
            source="enterprise",
            type=support_type if name == "SUPPORT" else None,
        )
        for name in feature_names
    }
    return LicenseInfo(
        id="test-license",
        type=type_,
        model=model,
        support_expires_at=expires_at,
        license_expires_at=None,
        features=features,
        serials=("TEST-000001",),
        enclosures={},
        contract_type=support_type,
    )


def make_facts(
    *,
    hardware_class: HardwareClass,
    license: LicenseInfo | None = None,
) -> EntitlementFacts:
    return EntitlementFacts(
        hardware_class=hardware_class,
        license=license,
    )


def facts_for_column(feature: str, column: str) -> EntitlementFacts:
    hardware_class = HardwareClass.TRUENAS_HW if column in ("HW", "HW+L", "HW+K") else HardwareClass.GENERIC
    if column in ("CE", "HW"):
        license = None
    elif column in ("HW+K", "CE+K"):
        license = make_license(feature_names=(feature,))
    else:  # HW+L / CE+L: licensed, but without this feature's key
        license = make_license(feature_names=())
    return make_facts(hardware_class=hardware_class, license=license)


# (a) Matrix fixture: every feature vector against every column resolves to the matrix cell.
@pytest.mark.parametrize("feature,column", [(f, c) for f in TARGET_VECTORS for c in COLUMNS])
def test_matrix_fixture(feature, column):
    cell = TARGET_VECTORS[feature][COLUMNS.index(column)]
    entitlement = check_entitlement(feature, facts_for_column(feature, column), policy=TARGET_VECTORS)
    assert entitlement.entitled == bool(cell)
    assert entitlement.column == column


# (b) Live POLICY shape: one entry per rule kind currently in active use.
def test_live_policy_shape():
    assert set(POLICY) == {
        LicenseFeature.DEDUP,
        LicenseFeature.DIRECTORY_SERVICES,
        LicenseFeature.FIBRECHANNEL,
        LicenseFeature.KMIP,
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
    assert isinstance(POLICY[LicenseFeature.DEDUP], Vector)
    assert isinstance(POLICY[LicenseFeature.DIRECTORY_SERVICES], Vector)
    assert isinstance(POLICY[LicenseFeature.FIBRECHANNEL], Vector)
    assert isinstance(POLICY[LicenseFeature.KMIP], Vector)
    assert isinstance(POLICY[LicenseFeature.ZFSTIER], Vector)
    assert isinstance(POLICY[LicenseFeature.APPS], Vector)
    assert isinstance(POLICY[LicenseFeature.CONTAINERS], Vector)
    assert isinstance(POLICY[LicenseFeature.VMS], Vector)
    assert isinstance(POLICY[LicenseFeature.WEBSHARE], Vector)
    assert isinstance(POLICY[LicenseFeature.STIG], Vector)
    assert isinstance(POLICY[LicenseFeature.SUPPORT], Vector)
    assert isinstance(POLICY[LicenseFeature.TRUESEARCH], Vector)
    assert isinstance(POLICY[LicenseFeature.NFS_SNAPSHOT], Vector)
    assert isinstance(POLICY[LicenseFeature.NVMEOF_SPDK], Vector)
    assert isinstance(POLICY[LicenseFeature.NETWORK_FEC], Vector)
    assert isinstance(POLICY[LicenseFeature.RDMA], Vector)
    assert isinstance(POLICY[LicenseFeature.SMB_FASTPATH], Vector)
    assert isinstance(POLICY[LicenseFeature.SMB_VEEAM], Vector)
    assert isinstance(POLICY[LicenseFeature.SED], LegacyRule)
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
    entitlement = check_entitlement(LicenseFeature.DEDUP, facts)
    assert entitlement.entitled is entitled
    assert entitlement.reason == reason
    assert entitlement.column == column


def test_dedup_no_license_message_uses_display_name():
    entitlement = check_entitlement(LicenseFeature.DEDUP, make_facts(hardware_class=HardwareClass.TRUENAS_HW))
    assert entitlement.message == "This system is not licensed to use the ZFS deduplication feature."


def test_dedup_key_missing_message_uses_display_name():
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license())
    entitlement = check_entitlement(LicenseFeature.DEDUP, facts)
    assert entitlement.message == "This system's license does not include the ZFS deduplication feature."


# ZFSTIER, STIG, SUPPORT, TRUESEARCH, NFS_SNAPSHOT, NVMEOF_SPDK, NETWORK_FEC, RDMA,
# WEBSHARE and DIRECTORY_SERVICES are live matrix Vectors (0,0,0,1,0,1): key-only on either
# hardware side.
KEY_ONLY_TABLE = [
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


@pytest.mark.parametrize(
    "feature",
    [
        LicenseFeature.ZFSTIER,
        LicenseFeature.STIG,
        LicenseFeature.SUPPORT,
        LicenseFeature.TRUESEARCH,
        LicenseFeature.NFS_SNAPSHOT,
        LicenseFeature.NVMEOF_SPDK,
        LicenseFeature.NETWORK_FEC,
        LicenseFeature.RDMA,
        LicenseFeature.SMB_FASTPATH,
        LicenseFeature.SMB_VEEAM,
        LicenseFeature.DIRECTORY_SERVICES,
        LicenseFeature.KMIP,
        LicenseFeature.WEBSHARE,
    ],
)
@pytest.mark.parametrize("hardware_class,state,entitled,reason,column", KEY_ONLY_TABLE)
def test_key_only_vector_behavior(feature, hardware_class, state, entitled, reason, column):
    facts = make_facts(hardware_class=hardware_class, license=_license_for(feature, state))
    entitlement = check_entitlement(feature, facts)
    assert entitlement.entitled is entitled
    assert entitlement.reason == reason
    assert entitlement.column == column


@pytest.mark.parametrize(
    "feature,display",
    [
        (LicenseFeature.ZFSTIER, "ZFS tiering"),
        (LicenseFeature.STIG, "STIG and FIPS"),
        (LicenseFeature.TRUESEARCH, "TrueSearch"),
        (LicenseFeature.RDMA, "RDMA"),
        (LicenseFeature.SMB_FASTPATH, "SMB ZFS fastpath"),
        (LicenseFeature.KMIP, "KMIP key management"),
        (LicenseFeature.WEBSHARE, "Webshare"),
    ],
)
def test_key_only_key_missing_message_uses_display_name(feature, display):
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license())
    entitlement = check_entitlement(feature, facts)
    assert entitlement.message == f"This system's license does not include the {display} feature."


# NFS_SNAPSHOT is a key-only vector too, but it keeps its pre-engine validation
# wording through FEATURE_MESSAGES instead of the generic display-name template.
NFS_SNAPSHOT_MESSAGE = "This is an enterprise feature and may not be enabled without a valid license."


def test_nfs_snapshot_bespoke_message_registered():
    overrides = FEATURE_MESSAGES[LicenseFeature.NFS_SNAPSHOT]
    for reason in (Reason.NO_LICENSE, Reason.KEY_MISSING, Reason.WRONG_HARDWARE):
        assert overrides[reason] == NFS_SNAPSHOT_MESSAGE


@pytest.mark.parametrize("hardware_class", [HardwareClass.TRUENAS_HW, HardwareClass.MINI, HardwareClass.GENERIC])
@pytest.mark.parametrize("state", ["none", "nokey"])
def test_nfs_snapshot_bespoke_message_from_live_policy(hardware_class, state):
    facts = make_facts(hardware_class=hardware_class, license=_license_for(LicenseFeature.NFS_SNAPSHOT, state))
    entitlement = check_entitlement(LicenseFeature.NFS_SNAPSHOT, facts)
    assert entitlement.entitled is False
    assert entitlement.message == NFS_SNAPSHOT_MESSAGE


def test_nfs_snapshot_bespoke_message_survives_vector_flip():
    # Dropping the CE key cell makes WRONG_HARDWARE reachable for this feature;
    # the wording must hold there too rather than falling back to the template.
    policy = {LicenseFeature.NFS_SNAPSHOT: Vector(0, 0, 0, 1, 0, 0)}
    facts = facts_for_column(LicenseFeature.NFS_SNAPSHOT, "CE+K")
    entitlement = check_entitlement(LicenseFeature.NFS_SNAPSHOT, facts, policy=policy)
    assert entitlement.entitled is False
    assert entitlement.reason == "WRONG_HARDWARE"
    assert entitlement.message == NFS_SNAPSHOT_MESSAGE


# FIBRECHANNEL is a live matrix Vector (0,0,1,1,0,1): any license grants it on iX
# hardware, while the CE side needs the key.
FIBRECHANNEL_TABLE = [
    (
        HardwareClass.TRUENAS_HW,
        "none",
        False,
        "NO_LICENSE",
        "HW",
        "This system is not licensed to use the Fibre Channel feature.",
    ),
    (HardwareClass.TRUENAS_HW, "nokey", True, "ENTITLED", "HW+L", ""),
    (HardwareClass.TRUENAS_HW, "key", True, "ENTITLED", "HW+K", ""),
    (
        HardwareClass.MINI,
        "none",
        False,
        "NO_LICENSE",
        "CE",
        "This system is not licensed to use the Fibre Channel feature.",
    ),
    (
        HardwareClass.MINI,
        "nokey",
        False,
        "KEY_MISSING",
        "CE+L",
        "This system's license does not include the Fibre Channel feature.",
    ),
    (HardwareClass.MINI, "key", True, "ENTITLED", "CE+K", ""),
    (
        HardwareClass.GENERIC,
        "none",
        False,
        "NO_LICENSE",
        "CE",
        "This system is not licensed to use the Fibre Channel feature.",
    ),
    (
        HardwareClass.GENERIC,
        "nokey",
        False,
        "KEY_MISSING",
        "CE+L",
        "This system's license does not include the Fibre Channel feature.",
    ),
    (HardwareClass.GENERIC, "key", True, "ENTITLED", "CE+K", ""),
]


@pytest.mark.parametrize("hardware_class,state,entitled,reason,column,message", FIBRECHANNEL_TABLE)
def test_fibrechannel_vector_behavior(hardware_class, state, entitled, reason, column, message):
    facts = make_facts(hardware_class=hardware_class, license=_license_for(LicenseFeature.FIBRECHANNEL, state))
    entitlement = check_entitlement(LicenseFeature.FIBRECHANNEL, facts)
    assert entitlement.entitled is entitled
    assert entitlement.reason == reason
    assert entitlement.column == column
    assert entitlement.message == message


# APPS, CONTAINERS and VMS are live matrix Vectors (1,1,0,1,0,1): granted with no
# license at all on either hardware side, but a license without the key revokes it.
WORKLOAD_TABLE = [
    (HardwareClass.TRUENAS_HW, "none", True, "ENTITLED", "HW"),
    (HardwareClass.TRUENAS_HW, "nokey", False, "KEY_MISSING", "HW+L"),
    (HardwareClass.TRUENAS_HW, "key", True, "ENTITLED", "HW+K"),
    (HardwareClass.MINI, "none", True, "ENTITLED", "CE"),
    (HardwareClass.MINI, "nokey", False, "KEY_MISSING", "CE+L"),
    (HardwareClass.MINI, "key", True, "ENTITLED", "CE+K"),
    (HardwareClass.GENERIC, "none", True, "ENTITLED", "CE"),
    (HardwareClass.GENERIC, "nokey", False, "KEY_MISSING", "CE+L"),
    (HardwareClass.GENERIC, "key", True, "ENTITLED", "CE+K"),
]


@pytest.mark.parametrize("feature", [LicenseFeature.APPS, LicenseFeature.CONTAINERS, LicenseFeature.VMS])
@pytest.mark.parametrize("hardware_class,state,entitled,reason,column", WORKLOAD_TABLE)
def test_workload_vector_behavior(feature, hardware_class, state, entitled, reason, column):
    facts = make_facts(hardware_class=hardware_class, license=_license_for(feature, state))
    entitlement = check_entitlement(feature, facts)
    assert entitlement.entitled is entitled
    assert entitlement.reason == reason
    assert entitlement.column == column


@pytest.mark.parametrize(
    "feature,display",
    [
        (LicenseFeature.APPS, "applications"),
        (LicenseFeature.CONTAINERS, "containers"),
        (LicenseFeature.VMS, "virtual machines"),
    ],
)
def test_workload_key_missing_message_uses_display_name(feature, display):
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license())
    entitlement = check_entitlement(feature, facts)
    assert entitlement.message == f"This system's license does not include the {display} feature."


# Nothing about the platform grants SPDK: an unlicensed system is denied on the
# license alone, whatever else is true of the hardware it runs on.
def test_nvmeof_spdk_unlicensed_denied_regardless_of_platform():
    facts = make_facts(hardware_class=HardwareClass.GENERIC)
    entitlement = check_entitlement(LicenseFeature.NVMEOF_SPDK, facts)
    assert entitlement.entitled is False
    assert entitlement.reason == "NO_LICENSE"
    assert entitlement.column == "CE"


# The license model is not consulted at all: keylessness alone decides, so a
# certified enterprise model is denied on the same terms as a freenas one.
@pytest.mark.parametrize("model", ["H10", "FREENAS-XYZ", None])
def test_nvmeof_spdk_licensed_without_key_denied_regardless_of_model(model):
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(model=model))
    entitlement = check_entitlement(LicenseFeature.NVMEOF_SPDK, facts)
    assert entitlement.entitled is False
    assert entitlement.reason == "KEY_MISSING"
    assert entitlement.column == "HW+L"


def test_nvmeof_spdk_unlicensed_no_license():
    facts = make_facts(hardware_class=HardwareClass.GENERIC)
    entitlement = check_entitlement(LicenseFeature.NVMEOF_SPDK, facts)
    assert entitlement.entitled is False
    assert entitlement.reason == "NO_LICENSE"
    assert entitlement.message == "SPDK is limited to enterprise licensed systems only."


# NVMEOF_SPDK carries a bespoke message via FEATURE_MESSAGES so the wording
# survived the flip from the LegacyRule to its matrix Vector.
def test_nvmeof_spdk_bespoke_message_registered():
    overrides = FEATURE_MESSAGES[LicenseFeature.NVMEOF_SPDK]
    for reason in (Reason.NO_LICENSE, Reason.KEY_MISSING, Reason.WRONG_HARDWARE):
        assert overrides[reason] == "SPDK is limited to enterprise licensed systems only."


def test_nvmeof_spdk_bespoke_message_survives_vector_flip():
    policy = {LicenseFeature.NVMEOF_SPDK: TARGET_VECTORS[LicenseFeature.NVMEOF_SPDK]}
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(feature_names=()))
    entitlement = check_entitlement(LicenseFeature.NVMEOF_SPDK, facts, policy=policy)
    assert entitlement.reason == "KEY_MISSING"
    assert entitlement.message == "SPDK is limited to enterprise licensed systems only."


# NETWORK_FEC is a key-only vector that keeps its pre-engine interface validation
# wording through FEATURE_MESSAGES rather than the generic display-name template.
NETWORK_FEC_MESSAGE = "Configuring FEC mode is an enterprise feature."


def test_network_fec_bespoke_message_registered():
    overrides = FEATURE_MESSAGES[LicenseFeature.NETWORK_FEC]
    for reason in (Reason.NO_LICENSE, Reason.KEY_MISSING, Reason.WRONG_HARDWARE):
        assert overrides[reason] == NETWORK_FEC_MESSAGE


@pytest.mark.parametrize("hardware_class", [HardwareClass.TRUENAS_HW, HardwareClass.MINI, HardwareClass.GENERIC])
@pytest.mark.parametrize("state", ["none", "nokey"])
def test_network_fec_bespoke_message_from_live_policy(hardware_class, state):
    facts = make_facts(hardware_class=hardware_class, license=_license_for(LicenseFeature.NETWORK_FEC, state))
    entitlement = check_entitlement(LicenseFeature.NETWORK_FEC, facts)
    assert entitlement.entitled is False
    assert entitlement.message == NETWORK_FEC_MESSAGE


def test_network_fec_bespoke_message_survives_vector_flip():
    policy = {LicenseFeature.NETWORK_FEC: TARGET_VECTORS[LicenseFeature.NETWORK_FEC]}
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(feature_names=()))
    entitlement = check_entitlement(LicenseFeature.NETWORK_FEC, facts, policy=policy)
    assert entitlement.reason == "KEY_MISSING"
    assert entitlement.message == NETWORK_FEC_MESSAGE


# SMB_VEEAM is a key-only vector that keeps its pre-engine share validation
# wording through FEATURE_MESSAGES rather than the generic display-name template.
SMB_VEEAM_MESSAGE = "Veeam repository shares require a TrueNAS enterprise license."


def test_smb_veeam_bespoke_message_registered():
    overrides = FEATURE_MESSAGES[LicenseFeature.SMB_VEEAM]
    for reason in (Reason.NO_LICENSE, Reason.KEY_MISSING, Reason.WRONG_HARDWARE):
        assert overrides[reason] == SMB_VEEAM_MESSAGE


@pytest.mark.parametrize("hardware_class", [HardwareClass.TRUENAS_HW, HardwareClass.MINI, HardwareClass.GENERIC])
@pytest.mark.parametrize("state", ["none", "nokey"])
def test_smb_veeam_bespoke_message_from_live_policy(hardware_class, state):
    facts = make_facts(hardware_class=hardware_class, license=_license_for(LicenseFeature.SMB_VEEAM, state))
    entitlement = check_entitlement(LicenseFeature.SMB_VEEAM, facts)
    assert entitlement.entitled is False
    assert entitlement.message == SMB_VEEAM_MESSAGE


def test_smb_veeam_bespoke_message_survives_vector_flip():
    policy = {LicenseFeature.SMB_VEEAM: Vector(0, 0, 0, 1, 0, 0)}
    facts = facts_for_column(LicenseFeature.SMB_VEEAM, "CE+K")
    entitlement = check_entitlement(LicenseFeature.SMB_VEEAM, facts, policy=policy)
    assert entitlement.entitled is False
    assert entitlement.reason == "WRONG_HARDWARE"
    assert entitlement.message == SMB_VEEAM_MESSAGE


# DIRECTORY_SERVICES gates directory-services authentication to the UI and API.
# It is a key-only vector that keeps its pre-engine system.general.update
# wording through FEATURE_MESSAGES rather than the generic display-name template.
DIRECTORY_SERVICES_MESSAGE = "Directory services authentication for UI and API access requires an Enterprise license."


def test_directory_services_bespoke_message_registered():
    overrides = FEATURE_MESSAGES[LicenseFeature.DIRECTORY_SERVICES]
    for reason in (Reason.NO_LICENSE, Reason.KEY_MISSING, Reason.WRONG_HARDWARE):
        assert overrides[reason] == DIRECTORY_SERVICES_MESSAGE


@pytest.mark.parametrize("hardware_class", [HardwareClass.TRUENAS_HW, HardwareClass.MINI, HardwareClass.GENERIC])
@pytest.mark.parametrize("state", ["none", "nokey"])
def test_directory_services_bespoke_message_from_live_policy(hardware_class, state):
    facts = make_facts(hardware_class=hardware_class, license=_license_for(LicenseFeature.DIRECTORY_SERVICES, state))
    entitlement = check_entitlement(LicenseFeature.DIRECTORY_SERVICES, facts)
    assert entitlement.entitled is False
    assert entitlement.message == DIRECTORY_SERVICES_MESSAGE


def test_directory_services_bespoke_message_survives_vector_flip():
    policy = {LicenseFeature.DIRECTORY_SERVICES: Vector(0, 0, 0, 1, 0, 0)}
    facts = facts_for_column(LicenseFeature.DIRECTORY_SERVICES, "CE+K")
    entitlement = check_entitlement(LicenseFeature.DIRECTORY_SERVICES, facts, policy=policy)
    assert entitlement.entitled is False
    assert entitlement.reason == "WRONG_HARDWARE"
    assert entitlement.message == DIRECTORY_SERVICES_MESSAGE


# SMB_FASTPATH is a key-only vector whose denial is silent in the smb.conf
# render, so it keeps the generic display-name wording.
def test_smb_fastpath_has_no_bespoke_message():
    assert LicenseFeature.SMB_FASTPATH not in FEATURE_MESSAGES


def test_legacy_sed_key_present_entitled():
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(feature_names=("SED",)))
    assert check_entitlement(LicenseFeature.SED, facts).entitled is True


def test_legacy_sed_expired_key_still_entitled():
    # Membership-only: an expired SED feature still counts.
    facts = make_facts(
        hardware_class=HardwareClass.TRUENAS_HW,
        license=make_license(feature_names=("SED",), expires_at=date.today() - timedelta(days=1)),
    )
    assert check_entitlement(LicenseFeature.SED, facts).entitled is True


def test_legacy_sed_no_key_key_missing():
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license())
    entitlement = check_entitlement(LicenseFeature.SED, facts)
    assert entitlement.entitled is False
    assert entitlement.reason == "KEY_MISSING"


def test_legacy_sed_no_license():
    entitlement = check_entitlement(LicenseFeature.SED, make_facts(hardware_class=HardwareClass.TRUENAS_HW))
    assert entitlement.entitled is False
    assert entitlement.reason == "NO_LICENSE"


# (d) Reason derivation from vectors.
def test_reason_fibrechannel_generic_no_license_is_no_license():
    entitlement = check_entitlement(
        LicenseFeature.FIBRECHANNEL, facts_for_column(LicenseFeature.FIBRECHANNEL, "CE"), policy=TARGET_VECTORS
    )
    assert entitlement.entitled is False
    assert entitlement.reason == "NO_LICENSE"


def test_reason_fibrechannel_generic_keyless_license_is_key_missing():
    entitlement = check_entitlement(
        LicenseFeature.FIBRECHANNEL, facts_for_column(LicenseFeature.FIBRECHANNEL, "CE+L"), policy=TARGET_VECTORS
    )
    assert entitlement.entitled is False
    assert entitlement.reason == "KEY_MISSING"


def test_reason_wrong_hardware():
    # Synthetic feature entitled only on HW+K -- a key on the CE side never grants it.
    policy = {"SYNTHETIC_HW_ONLY": Vector(0, 0, 0, 1, 0, 0)}
    entitlement = check_entitlement("SYNTHETIC_HW_ONLY", facts_for_column("SYNTHETIC_HW_ONLY", "CE+K"), policy=policy)
    assert entitlement.entitled is False
    assert entitlement.reason == "WRONG_HARDWARE"


# (e) Revocation rule: a license lacking the key revokes a bare no-license grant.
def test_revocation_apps_generic_no_license_entitled():
    entitlement = check_entitlement(
        LicenseFeature.APPS, facts_for_column(LicenseFeature.APPS, "CE"), policy=TARGET_VECTORS
    )
    assert entitlement.entitled is True
    assert entitlement.column == "CE"


def test_revocation_apps_generic_keyless_license_revoked():
    entitlement = check_entitlement(
        LicenseFeature.APPS, facts_for_column(LicenseFeature.APPS, "CE+L"), policy=TARGET_VECTORS
    )
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
    support = facts.license.features["SUPPORT"]
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
        check_entitlement("NOPE", make_facts(hardware_class=HardwareClass.GENERIC))


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
    entitlement = check_entitlement(DerivedEntitlement.PROACTIVE_SUPPORT, facts)
    assert entitlement.entitled is entitled
    assert entitlement.reason == reason


def test_proactive_support_key_absent_is_key_missing():
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(feature_names=()))
    entitlement = check_entitlement(DerivedEntitlement.PROACTIVE_SUPPORT, facts)
    assert entitlement.entitled is False
    assert entitlement.reason == "KEY_MISSING"


def test_proactive_support_unlicensed_is_no_license():
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW)
    entitlement = check_entitlement(DerivedEntitlement.PROACTIVE_SUPPORT, facts)
    assert entitlement.entitled is False
    assert entitlement.reason == "NO_LICENSE"


# (j) HA: live LicenseTypeRule over the license type.
def test_ha_entitled_for_enterprise_ha():
    facts = make_facts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(type_=LicenseType.ENTERPRISE_HA))
    assert check_entitlement(DerivedEntitlement.HA, facts).entitled is True


def test_ha_wrong_type_for_enterprise_single():
    facts = make_facts(
        hardware_class=HardwareClass.TRUENAS_HW,
        license=make_license(type_=LicenseType.ENTERPRISE_SINGLE),
    )
    entitlement = check_entitlement(DerivedEntitlement.HA, facts)
    assert entitlement.entitled is False
    assert entitlement.reason == "WRONG_LICENSE_TYPE"


def test_ha_unlicensed_is_no_license():
    entitlement = check_entitlement(DerivedEntitlement.HA, make_facts(hardware_class=HardwareClass.TRUENAS_HW))
    assert entitlement.entitled is False
    assert entitlement.reason == "NO_LICENSE"


# HA is decided by the license type alone. Hardware class only names the column, so an
# ENTERPRISE_HA license grants it on every hardware class and an ENTERPRISE_SINGLE one
# grants it on none. These fail if HA is ever given a matrix Vector, since a Vector would
# make the answer depend on the hardware side and on a LicenseFeature.HA key that does
# not exist.
@pytest.mark.parametrize("hardware_class", [HardwareClass.GENERIC, HardwareClass.MINI])
def test_ha_license_type_grants_on_any_hardware_class(hardware_class):
    facts = make_facts(hardware_class=hardware_class, license=make_license(type_=LicenseType.ENTERPRISE_HA))
    assert check_entitlement(DerivedEntitlement.HA, facts).entitled is True


def test_ha_not_granted_by_hardware_class_alone():
    facts = make_facts(
        hardware_class=HardwareClass.TRUENAS_HW,
        license=make_license(type_=LicenseType.ENTERPRISE_SINGLE),
    )
    entitlement = check_entitlement(DerivedEntitlement.HA, facts)
    assert entitlement.entitled is False
    assert entitlement.reason == "WRONG_LICENSE_TYPE"
