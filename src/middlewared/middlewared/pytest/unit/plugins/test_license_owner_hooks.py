import importlib
from unittest.mock import AsyncMock

import pytest

from middlewared.plugins.iscsi_ import iscsi_global
from middlewared.pytest.unit.middleware import Middleware, fake_service_control

nvmet_global = importlib.import_module("middlewared.plugins.nvmet.global")


@pytest.mark.parametrize("hook", [iscsi_global.hook_license_update_iscsi, nvmet_global.hook_license_update_nvmet])
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
