import json

import pytest
from truenas_pylicensed import LicenseType

from middlewared.api.base.handler.accept import accept_params
from middlewared.api.base.handler.result import serialize_result
from middlewared.api.current import TrueNASEntitlementsInfoResult
from middlewared.plugins.truenas import entitlements as plugin
from middlewared.plugins.truenas.entitlements import (
    TrueNASEntitlementsCheckArgs,
    TrueNASEntitlementsCheckEntitlement,
    TrueNASEntitlementsCheckResult,
    TrueNASEntitlementsService,
)
from middlewared.service_exception import ValidationErrors
from middlewared.utils.entitlements import (
    COLUMNS,
    POLICY,
    DerivedEntitlement,
    Entitlement,
    EntitlementFacts,
    HardwareClass,
    LicenseFeature,
    Reason,
)
from middlewared.utils.license import FeatureInfo, LicenseInfo


def test_check_returns_the_endpoint_model_not_the_engine_dataclass(monkeypatch):
    """The engine's dataclass must not escape through the endpoint: the model is the type every
    mock and stub of this method has to imitate."""
    monkeypatch.setattr(
        plugin,
        "get_entitlement",
        lambda feature: Entitlement(entitled=True, reason=Reason.ENTITLED, column="HW+K", message=""),
    )

    result = TrueNASEntitlementsService.check(None, "SED")

    assert isinstance(result, TrueNASEntitlementsCheckEntitlement)
    assert not isinstance(result, Entitlement)
    assert (result.entitled, result.reason, result.column, result.message) == (True, "ENTITLED", "HW+K", "")


@pytest.mark.parametrize("column", COLUMNS)
@pytest.mark.parametrize("reason", list(Reason))
def test_entitlement_round_trips_to_json(reason, column, monkeypatch):
    engine_result = Entitlement(
        entitled=reason is Reason.ENTITLED,
        reason=reason,
        column=column,
        message="" if reason is Reason.ENTITLED else f"denied: {reason}",
    )
    monkeypatch.setattr(plugin, "get_entitlement", lambda feature: engine_result)

    result = serialize_result(
        TrueNASEntitlementsCheckResult, TrueNASEntitlementsService.check(None, "SED"), True, False
    )

    assert result == {
        "entitled": engine_result.entitled,
        "reason": str(reason),
        "column": column,
        "message": engine_result.message,
    }
    assert type(result["reason"]) is str
    assert json.loads(json.dumps(result)) == result


@pytest.mark.parametrize("member", [LicenseFeature.SED, DerivedEntitlement.HA])
def test_entitlement_key_member_survives_the_boundary_unchanged(member):
    """Both vocabularies are accepted, and a member is handed on as itself rather than reduced
    to its value."""
    (feature,) = accept_params(TrueNASEntitlementsCheckArgs, [member], dump_models=False)

    assert feature is member


@pytest.mark.parametrize("name,expected", [("SED", LicenseFeature.SED), ("HA", DerivedEntitlement.HA)])
def test_feature_name_coerces_to_its_enum_member(name, expected):
    """A caller over the wire can only send a string, so the boundary has to resolve it against
    both vocabularies."""
    (feature,) = accept_params(TrueNASEntitlementsCheckArgs, [name], dump_models=False)

    assert feature is expected


def test_unknown_feature_name_is_rejected_at_the_boundary():
    """An unrecognized name must not reach the engine, and the rejection has to say why."""
    with pytest.raises(ValidationErrors) as exc_info:
        accept_params(TrueNASEntitlementsCheckArgs, ["NOT_A_FEATURE"], dump_models=False)

    assert "neither a license feature nor a derived entitlement" in str(exc_info.value)


def make_license(feature_names, license_type, support_type):
    features = {
        name: FeatureInfo(
            name=name,
            start_date=None,
            expires_at=None,
            source="enterprise",
            type=support_type if name == "SUPPORT" else None,
        )
        for name in feature_names
    }
    return LicenseInfo(
        id="test-license",
        type=license_type,
        model="H10",
        support_expires_at=None,
        license_expires_at=None,
        features=features,
        serials=("TEST-000001",),
        enclosures={},
        contract_type=support_type,
    )


UNLICENSED_APPLIANCE = EntitlementFacts(hardware_class=HardwareClass.TRUENAS_HW, license=None)

# Fact shapes that between them reach every reason the live policy can produce, so the
# whole-map assertions below are exercised against grants and every kind of denial.
FACTS_TABLE = [
    UNLICENSED_APPLIANCE,
    EntitlementFacts(hardware_class=HardwareClass.GENERIC, license=None),
    EntitlementFacts(
        hardware_class=HardwareClass.TRUENAS_HW,
        license=make_license((), LicenseType.ENTERPRISE_SINGLE, None),
    ),
    EntitlementFacts(
        hardware_class=HardwareClass.TRUENAS_HW,
        license=make_license(tuple(LicenseFeature), LicenseType.ENTERPRISE_HA, "GOLD"),
    ),
    EntitlementFacts(
        hardware_class=HardwareClass.GENERIC,
        license=make_license(tuple(LicenseFeature), LicenseType.ENTERPRISE_SINGLE, "BRONZE"),
    ),
]


@pytest.mark.parametrize("facts", FACTS_TABLE)
def test_info_reports_every_policy_feature_and_nothing_else(facts, monkeypatch):
    monkeypatch.setattr(plugin, "get_facts", lambda: facts)

    assert set(TrueNASEntitlementsService.info(None).features) == {str(key) for key in POLICY}


@pytest.mark.parametrize("feature", [LicenseFeature.AUTOTUNE, LicenseFeature.LTS])
def test_info_omits_a_license_feature_the_policy_does_not_rule_on(feature, monkeypatch):
    """These two carry a matrix row but no policy entry, and the engine raises for a key it
    cannot resolve -- so enumerating the feature vocabulary here would fail outright."""
    monkeypatch.setattr(plugin, "get_facts", lambda: UNLICENSED_APPLIANCE)

    assert str(feature) not in TrueNASEntitlementsService.info(None).features


@pytest.mark.parametrize("facts", FACTS_TABLE)
def test_info_round_trips_to_json_without_the_matrix_column(facts, monkeypatch):
    monkeypatch.setattr(plugin, "get_facts", lambda: facts)

    result = serialize_result(TrueNASEntitlementsInfoResult, TrueNASEntitlementsService.info(None), True, False)

    assert json.loads(json.dumps(result)) == result
    assert "column" not in json.dumps(result)
    for feature, entry in result["features"].items():
        assert set(entry) == {"entitled", "reason", "message"}, feature
        assert type(entry["reason"]) is str, feature


@pytest.mark.parametrize("facts", FACTS_TABLE)
def test_info_carries_a_message_exactly_where_it_denies(facts, monkeypatch):
    monkeypatch.setattr(plugin, "get_facts", lambda: facts)

    for feature, entry in TrueNASEntitlementsService.info(None).features.items():
        assert (entry.message == "") is entry.entitled, feature


def test_info_reads_the_system_facts_once(monkeypatch):
    """One facts read answers the whole map. `get_facts()` is uncached and its license read is
    a round trip to the license daemon, so a read per feature is a round trip per key."""
    reads = []

    def counting_get_facts():
        reads.append(None)
        return UNLICENSED_APPLIANCE

    monkeypatch.setattr(plugin, "get_facts", counting_get_facts)

    result = TrueNASEntitlementsService.info(None)

    assert len(reads) == 1
    assert len(result.features) == len(POLICY)
