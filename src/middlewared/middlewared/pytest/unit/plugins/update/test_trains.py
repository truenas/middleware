import pytest
from unittest.mock import AsyncMock, Mock

from middlewared.plugins.update_.trains import Trains, UpdateService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.asyncio
@pytest.mark.parametrize("manifest,trains,result", [
    # Redirects current train if it was renamed
    (
        Mock(train="TrueNAS-Fangtooth-RC"),
        {"trains": {"TrueNAS-SCALE-Fangtooth": {}},
         "trains_redirection": {"TrueNAS-Fangtooth-RC": "TrueNAS-SCALE-Fangtooth"}},
        Trains.model_validate({
            "trains": {"TrueNAS-SCALE-Fangtooth": {}},
            "trains_redirection": {"TrueNAS-Fangtooth-RC": "TrueNAS-SCALE-Fangtooth"}
        }),
    ),
    # Inserts current train as DEVELOPER profile if it does not exist
    # in the update trains file
    (
        Mock(train="TrueNAS-SCALE-Goldeye-Nightlies"),
        {"trains": {"TrueNAS-SCALE-Fangtooth": {}},
         "trains_redirection": {}},
        Trains.model_validate({
            "trains": {"TrueNAS-SCALE-Fangtooth": {},
                       "TrueNAS-SCALE-Goldeye-Nightlies": {}},
            "trains_redirection": {}
        }),
    ),
])
async def test_update_get_trains(manifest, trains, result):
    middleware = Middleware()
    middleware.services.update.get_manifest_file = Mock(return_value=manifest)

    service = UpdateService(middleware)
    service.fetch = AsyncMock(return_value=trains)

    assert await service.get_trains() == result


@pytest.mark.asyncio
@pytest.mark.parametrize("trains,current_train_name,result", [
    # Can be upgraded to tne next immediate train
    (
        Trains.model_validate({"trains": {"TrueNAS-SCALE-Cobia": {},
                                          "TrueNAS-SCALE-Dragonfish": {},
                                          "TrueNAS-SCALE-ElectricEel": {},
                                          "TrueNAS-SCALE-Fangtooth": {}}}),
        "TrueNAS-SCALE-Dragonfish",
        ["TrueNAS-SCALE-ElectricEel", "TrueNAS-SCALE-Dragonfish"],
    ),
    # Already on the newest train
    (
        Trains.model_validate({"trains": {"TrueNAS-SCALE-Cobia": {},
                                          "TrueNAS-SCALE-Dragonfish": {},
                                          "TrueNAS-SCALE-ElectricEel": {},
                                          "TrueNAS-SCALE-Fangtooth": {}}}),
        "TrueNAS-SCALE-Fangtooth",
        ["TrueNAS-SCALE-Fangtooth"],
    ),
])
async def test_update_get_next_trains_names(trains, current_train_name, result):
    service = UpdateService(Mock())
    service.get_current_train_name = AsyncMock(return_value=current_train_name)

    assert await service.get_next_trains_names(trains) == result
