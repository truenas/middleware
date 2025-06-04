import pytest
from unittest.mock import Mock

from middlewared.plugins.update_.profile import UpdateService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.asyncio
async def test_update_available_versions():
    middleware = Middleware()
    middleware["system.is_enterprise"] = Mock(return_value=True)
    middleware["update.get_manifest_file"] = Mock(return_value={"update_profile": "CONSERVATIVE"})

    service = UpdateService(middleware)

    choices = await service.profile_choices()
    assert list(choices.keys()) == ["GENERAL", "CONSERVATIVE", "MISSION_CRITICAL"]
    assert choices["GENERAL"]["available"]
    assert choices["CONSERVATIVE"]["available"]
    assert not choices["MISSION_CRITICAL"]["available"]
