from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.alert.source.webshare import WebshareStoppedAlert
from middlewared.plugins.webshare.utils import reconcile


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
    middleware.call = AsyncMock(return_value=True)
    actions = []
    alerts = []

    async def call2(method, *args):
        if method is middleware.services.service.query:
            return Mock(state="RUNNING", enable=True)
        if method is middleware.services.webshare.start_blocker:
            return blocker
        if method is middleware.services.service.control:
            actions.append(args[0])
            return Mock(wait=AsyncMock())
        if method is middleware.services.alert.oneshot_create:
            alerts.extend(args)

    middleware.call2 = call2

    await reconcile(middleware)

    assert actions == [action]
    assert [type(alert) for alert in alerts] == ([WebshareStoppedAlert] if alert_created else [])
