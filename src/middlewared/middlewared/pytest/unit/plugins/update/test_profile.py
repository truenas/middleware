import pytest
from unittest.mock import AsyncMock, Mock

from middlewared.plugins.update_.profile_ import UpdateService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.asyncio
async def test_profile_choices():
    middleware = Middleware()
    middleware["system.is_enterprise"] = Mock(return_value=True)
    middleware.services.update.config_internal = Mock(return_value=Mock(profile=None))

    service = UpdateService(middleware)
    service.current_version_profile = AsyncMock(return_value="GENERAL")

    choices = await service.profile_choices()
    assert list(choices.keys()) == ["GENERAL", "MISSION_CRITICAL"]
    assert choices["GENERAL"].available
    assert not choices["MISSION_CRITICAL"].available


@pytest.mark.asyncio
async def test_profile_choices_current_is_always_available():
    middleware = Middleware()
    middleware["system.is_enterprise"] = Mock(return_value=True)
    middleware.services.update.config_internal = Mock(return_value=Mock(profile="MISSION_CRITICAL"))

    service = UpdateService(middleware)
    service.current_version_profile = AsyncMock(return_value="GENERAL")

    choices = await service.profile_choices()
    assert list(choices.keys()) == ["GENERAL", "MISSION_CRITICAL"]
    assert choices["GENERAL"].available
    assert choices["MISSION_CRITICAL"].available
