import json

import pytest

from middlewared.api.base.handler.result import serialize_result
from middlewared.plugins.truenas import entitlements as plugin
from middlewared.plugins.truenas.entitlements import (
    TrueNASEntitlementsCheckEntitlement,
    TrueNASEntitlementsCheckResult,
    TrueNASEntitlementsService,
)
from middlewared.utils.entitlements import COLUMNS, Entitlement, Reason


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
