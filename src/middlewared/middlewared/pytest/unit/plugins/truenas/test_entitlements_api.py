import json

import pytest
from truenas_pylicensed import LicenseType

from middlewared.api.base.handler.result import serialize_result
from middlewared.api.current import (
    EntitlementEntry,
    TrueNASEntitlementsCheckResult,
    TrueNASEntitlementsInfoResult,
)
from middlewared.plugins.truenas import entitlements as plugin
from middlewared.service import CallError
from middlewared.plugins.truenas.entitlements import TrueNASEntitlementsService
from middlewared.utils.entitlements import (
    POLICY,
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

    assert isinstance(result, EntitlementEntry)
    assert not isinstance(result, Entitlement)
    assert (result.entitled, result.reason, result.message) == (True, "ENTITLED", "")


@pytest.mark.parametrize("reason", [Reason.ENTITLED, Reason.KEY_MISSING])
def test_entitlement_round_trips_to_json(reason, monkeypatch):
    engine_result = Entitlement(
        entitled=reason is Reason.ENTITLED,
        reason=reason,
        column="HW+K",
        message="" if reason is Reason.ENTITLED else f"denied: {reason}",
    )
    monkeypatch.setattr(plugin, "get_entitlement", lambda feature: engine_result)

    result = serialize_result(
        TrueNASEntitlementsCheckResult, TrueNASEntitlementsService.check(None, "SED"), True, False
    )

    assert result == {
        "entitled": engine_result.entitled,
        "reason": str(reason),
        "message": engine_result.message,
    }
    assert type(result["reason"]) is str
    assert json.loads(json.dumps(result)) == result


def test_feature_reports_not_gated_for_an_unknown_identifier(monkeypatch):
    """The issuer's vocabulary can run ahead of ours, so the public endpoint answers for a name
    it has never heard of instead of refusing it."""

    def raise_unknown(feature):
        raise ValueError(f"Unknown feature: {feature!r}")

    monkeypatch.setattr(plugin, "get_entitlement", raise_unknown)

    result = TrueNASEntitlementsService.check(None, "QUANTUM_TELEPORT")

    assert (result.entitled, result.reason, result.message) == (True, "NOT_GATED", "")


def test_feature_does_not_swallow_an_engine_bug(monkeypatch):
    """Only the engine's `ValueError` for an unruled key is an answer. Anything else reaches the
    caller as a CallError naming the feature, with the original chained to it."""

    def raise_bug(feature):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(plugin, "get_entitlement", raise_bug)

    with pytest.raises(CallError) as exc:
        TrueNASEntitlementsService.check(None, "SED")

    assert "SED" in str(exc.value)
    assert isinstance(exc.value.__context__, RuntimeError)


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
        features=features,
        serials=("TEST-000001",),
        enclosures={},
        contract_type=support_type,
    )


UNLICENSED_APPLIANCE = EntitlementFacts(hardware_class=HardwareClass.TRUENAS_HW, license=None)

# One shape with no license and one with every key, so the whole-map assertions below run
# against a map that is mostly grants and a map that is mostly denials.
FACTS_TABLE = [
    UNLICENSED_APPLIANCE,
    EntitlementFacts(
        hardware_class=HardwareClass.GENERIC,
        license=make_license(tuple(LicenseFeature), LicenseType.ENTERPRISE_SINGLE, "BRONZE"),
    ),
]


@pytest.mark.parametrize("facts", FACTS_TABLE)
def test_info_reports_every_policy_feature_and_nothing_else(facts, monkeypatch):
    monkeypatch.setattr(plugin, "get_facts", lambda: facts)

    assert set(TrueNASEntitlementsService.info(None).features) == {str(key) for key in POLICY}


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
