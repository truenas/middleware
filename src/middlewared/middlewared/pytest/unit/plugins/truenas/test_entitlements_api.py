import json

import pytest

from middlewared.api.base.handler.accept import accept_params
from middlewared.api.base.handler.result import serialize_result
from middlewared.plugins.truenas import entitlements as plugin
from middlewared.plugins.truenas.entitlements import (
    TrueNASEntitlementsCheckArgs,
    TrueNASEntitlementsCheckEntitlement,
    TrueNASEntitlementsCheckResult,
    TrueNASEntitlementsService,
)
from middlewared.service_exception import ValidationErrors
from middlewared.utils.entitlements import COLUMNS, DerivedEntitlement, Entitlement, LicenseFeature, Reason


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
