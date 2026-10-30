import importlib
from unittest.mock import AsyncMock

import pytest

from middlewared.plugins import cron, failover, network, smb
from middlewared.plugins import service as service_plugin
from middlewared.plugins.iscsi_ import iscsi_global
from middlewared.pytest.unit.middleware import Middleware, fake_service_control

nvmet_global = importlib.import_module("middlewared.plugins.nvmet.global")


@pytest.mark.parametrize(
    "hook",
    [
        iscsi_global.hook_license_update_iscsi,
        nvmet_global.hook_license_update_nvmet,
        smb.hook_license_update_cifs,
        failover.hook_license_update_ctdb,
        network.hook_license_update_discovery,
        service_plugin.hook_license_update_rc,
        cron.hook_license_update_cron,
    ],
)
@pytest.mark.asyncio
async def test_unchanged_license_issues_nothing(hook):
    m = Middleware()
    calls = fake_service_control(m)
    generated = []
    m["etc.generate"] = lambda *args: generated.append(args)
    m.services.service.started = AsyncMock(return_value=True)
    m["nvmet.global.running"] = AsyncMock(return_value=True)

    await hook(m, changed=frozenset())

    assert calls == []
    assert generated == []


@pytest.mark.parametrize("started,expected", [(False, [("START", "ctdb")]), (True, [])])
@pytest.mark.asyncio
async def test_ha_grant_starts_ctdb_only_when_stopped(started, expected):
    m = Middleware()
    calls = fake_service_control(m)
    m["etc.generate"] = lambda *args: None
    m["failover.licensed"] = AsyncMock(return_value=True)
    m.services.service.started = AsyncMock(return_value=started)

    await failover.hook_license_update_ctdb(m, changed=frozenset({"HA"}))

    assert [(verb, service) for verb, service, _ in calls] == expected
