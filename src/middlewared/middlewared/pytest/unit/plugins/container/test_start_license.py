import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.plugins.container import lifecycle
from middlewared.service_exception import CallError


def test_start_refuses_when_unlicensed():
    """Containers starting on a system whose license does not grant them."""
    context = Mock()
    context.call2 = AsyncMock(return_value=Mock(entitled=False))
    context.run_coroutine = asyncio.run

    with pytest.raises(CallError, match="not licensed to use containers"):
        lifecycle.start(context, 1)

    context.middleware.libvirt_domains_manager.containers.start.assert_not_called()
