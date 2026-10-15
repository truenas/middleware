from unittest.mock import AsyncMock

import pytest

from middlewared.plugins import failover
from middlewared.pytest.unit.middleware import Middleware, fake_service_control


@pytest.mark.asyncio
async def test_grant_starts_stopped_ctdb(monkeypatch):
    """A newly HA-licensed node has ctdb stopped, and a RESTART of a stopped unit is skipped."""
    monkeypatch.setattr(failover, "_start_stop_vrrp_threads", AsyncMock())
    m = Middleware()
    m["failover.ensure_remote_client"] = AsyncMock()
    m["etc.generate"] = AsyncMock()
    m["nvmet.global.running"] = AsyncMock(return_value=False)
    m.services.service.started = lambda service: False
    calls = fake_service_control(m, True)

    await failover.HALicenseDelegate(m).apply({"HA": True})

    assert ("START", "ctdb") in [(verb, service) for verb, service, options in calls]
