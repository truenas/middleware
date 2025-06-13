import pytest
from unittest.mock import Mock

from middlewared.plugins.update_.version import UpdateService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.asyncio
@pytest.mark.parametrize("current_train_name,trains,trains_manifests,result", [
    (
        "TrueNAS-SCALE-ElectricEel",
        {"trains": {"TrueNAS-SCALE-Dragonfish": {},
                    "TrueNAS-SCALE-ElectricEel": {},
                    "TrueNAS-SCALE-Fangtooth": {}}},
        {"TrueNAS-SCALE-ElectricEel": {"version": "24.10.2", "url": "https://truenas.com/dl/24.10.2"},
         "TrueNAS-SCALE-Fangtooth": {"version": "25.04.1", "url": "https://truenas.com/dl/25.04.1"}},
        [
            {"train": "TrueNAS-SCALE-ElectricEel", "version": {"version": "24.10.2",
                                                               "manifest": {"version": "24.10.2",
                                                                            "url": "https://truenas.com/dl/24.10.2"},
                                                               "release_notes_url": "https://truenas.com/24.10.2"}},
            {"train": "TrueNAS-SCALE-Fangtooth", "version": {"version": "25.04.1",
                                                             "manifest": {"version": "25.04.1",
                                                                          "url": "https://truenas.com/dl/25.04.1"},
                                                             "release_notes_url": "https://truenas.com/25.04.1"}},
        ]
    ),
])
async def test_update_available_versions(current_train_name, trains, trains_manifests, result):
    middleware = Middleware()
    middleware["update.get_current_train_name"] = Mock(return_value=current_train_name)
    middleware["update.get_trains"] = Mock(return_value=trains)
    middleware["update.get_train_manifest"] = Mock(side_effect=lambda train: trains_manifests[train])
    middleware["system.release_notes_url"] = Mock(side_effect=lambda version: f"https://truenas.com/{version}")

    service = UpdateService(middleware)

    assert await service.available_versions() == result
