import pytest
from unittest.mock import AsyncMock, Mock

from middlewared.plugins.update_.trains import UpdateService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.asyncio
@pytest.mark.parametrize("manifest,trains,result", [
    # Redirects current train if it was renamed
    (
        {"train": "TrueNAS-Fangtooth-RC"},
        {"trains": {"TrueNAS-SCALE-Fangtooth": {"update_profile": "GENERAL"}},
         "trains_redirection": {"TrueNAS-Fangtooth-RC": "TrueNAS-SCALE-Fangtooth"}},
        {"trains": {"TrueNAS-SCALE-Fangtooth": {"update_profile": "GENERAL"}},
         "trains_redirection": {"TrueNAS-Fangtooth-RC": "TrueNAS-SCALE-Fangtooth"}},
    ),
    # Inserts current train as DEVELOPER profile if it does not exist in `trains.json`
    (
        {"train": "TrueNAS-SCALE-Goldeye-Nightlies"},
        {"trains": {"TrueNAS-SCALE-Fangtooth": {"update_profile": "GENERAL"}},
         "trains_redirection": {}},
        {"trains": {"TrueNAS-SCALE-Fangtooth": {"update_profile": "GENERAL"},
                    "TrueNAS-SCALE-Goldeye-Nightlies": {"update_profile": "DEVELOPER"}},
         "trains_redirection": {}},
    ),
])
async def test_update_get_trains(manifest, trains, result):
    middleware = Middleware()
    middleware["update.get_manifest_file"] = Mock(return_value=manifest)

    service = UpdateService(middleware)
    service.fetch = AsyncMock(return_value=trains)

    assert await service.get_trains() == result
