from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.api.current import ServiceOptions
from middlewared.auth import TruenasNodeSessionManagerCredentials
from middlewared.plugins import service as service_plugin
from middlewared.plugins.service import ServiceService
from middlewared.pytest.unit.middleware import Middleware


class _Stop(Exception):
    pass


def _user():
    return Mock(authenticated_credentials=Mock(is_user_session=True))


def _node():
    return Mock(authenticated_credentials=TruenasNodeSessionManagerCredentials())


ACTIONS = {
    "STOP": ("stop", False, True),
    "RESTART": ("restart", False, True),
    "RELOAD_RUNNING_NOT_RELOADABLE": ("reload", False, True),
    "RELOAD_STOPPED": ("reload", False, False),
    "RELOAD_RELOADABLE": ("reload", True, True),
}
CUTS = {"STOP", "RESTART", "RELOAD_RUNNING_NOT_RELOADABLE"}


@pytest.mark.parametrize("caller", ["user", "node", "internal"])
@pytest.mark.parametrize("action", list(ACTIONS))
@pytest.mark.asyncio
async def test_user_actions_cut(monkeypatch, caller, action):
    method, reloadable, running = ACTIONS[action]
    app = {"user": _user, "node": _node, "internal": lambda: None}[caller]()

    m = Middleware()
    svc = ServiceService(m)
    service_object = SimpleNamespace(
        reloadable=reloadable,
        get_state=AsyncMock(return_value=SimpleNamespace(running=running)),
    )
    monkeypatch.setattr(svc, "object", AsyncMock(return_value=service_object))
    monkeypatch.setattr(service_plugin, "app_has_write_privilege_for_service", lambda *a: True)
    m.services.truenas.entitlements.cut_service = AsyncMock()
    m.call_hook = AsyncMock(side_effect=_Stop)

    with pytest.raises(_Stop):
        await getattr(svc, method)(app, "nfs", ServiceOptions())

    if caller == "user" and action in CUTS:
        m.services.truenas.entitlements.cut_service.assert_awaited_once_with("nfs")
    else:
        m.services.truenas.entitlements.cut_service.assert_not_awaited()
