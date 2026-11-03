from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.plugins.webshare.config import reconcile


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "blocker,action,alert_created",
    [
        ("Webshare requires TrueNAS Connect to be configured.", "STOP", True),
        (None, "RESTART", False),
    ],
)
async def test_reconcile(blocker, action, alert_created):
    middleware = Mock()
    actions = []
    alerts = []

    async def call(method, *args):
        if method == "failover.is_single_master_node":
            return True
        if method == "service.query":
            return {"state": "RUNNING", "enable": True}
        if method == "service.control":
            actions.append(args[0])
            return Mock(wait=AsyncMock())
        if method == "alert.oneshot_create":
            alerts.append(args[0])

    middleware.call = call
    middleware.call2 = AsyncMock(return_value=blocker)

    await reconcile(middleware)

    assert actions == [action]
    assert alerts == (["WebshareStopped"] if alert_created else [])
