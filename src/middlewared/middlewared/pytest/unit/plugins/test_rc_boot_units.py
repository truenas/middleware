import importlib.util
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.service.services.ssh import SSHService
from middlewared.plugins.service.services.webshare import WebShareService
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.middleware import Middleware


def _load_rc_renderer():
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "etc_files", "systemd.py")
    spec = importlib.util.spec_from_file_location("rc_systemd", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_rc_enables_units_from_boot_decision(monkeypatch, tmp_path):
    rc = _load_rc_renderer()
    m = Middleware()
    install_entitlements_for_column(m, LicenseFeature.WEBSHARE, "CE")
    objects = {
        "webshare": WebShareService(m),
        "ssh": SSHService(m),
        "iscsitarget": SimpleNamespace(may_enable_at_boot=AsyncMock(return_value=True)),
    }
    units = {"webshare": ["truenas-webshare-auth"], "ssh": ["ssh"], "iscsitarget": ["scst"]}
    m["datastore.query"] = lambda *args: [{"service": name, "enable": True} for name in objects]
    m["failover.licensed"] = AsyncMock(return_value=True)
    m["iscsi.global.lio_enabled"] = AsyncMock(return_value=False)
    m.services.service.object = lambda name: objects[name]
    m.services.service.systemd_units = lambda name: units[name]

    dbus = Mock(get_unit_file_state=AsyncMock(return_value="enabled"), set_unit_file_state=AsyncMock())
    monkeypatch.setattr(rc, "system_dbus", dbus)
    json_path = tmp_path / "user-services.json"
    monkeypatch.setattr(rc, "atomic_write", lambda path, mode, perms: open(json_path, mode))

    await rc.render(None, m)

    assert dbus.set_unit_file_state.await_args_list == [call("truenas-webshare-auth", False), call("scst", False)]
    assert json.loads(json_path.read_text()) == {"truenas-webshare-auth": False, "ssh": True, "scst": True}
