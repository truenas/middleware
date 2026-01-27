import pytest
from unittest.mock import AsyncMock, Mock, patch

from middlewared.plugins.update_.trains import Trains, get_trains, get_next_trains_names
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
    middleware["network.general.will_perform_activity"] = AsyncMock()

    with patch('middlewared.plugins.update_.trains.fetch', new=AsyncMock(return_value=trains)), \
         patch('middlewared.plugins.update_.trains.get_manifest_file', return_value=manifest):
        assert await get_trains(middleware) == result


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
    middleware = Middleware()

    with patch('middlewared.plugins.update_.trains.get_current_train_name',
               AsyncMock(return_value=current_train_name)):
        assert await get_next_trains_names(middleware, trains) == result
