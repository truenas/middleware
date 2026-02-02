import pytest
from unittest.mock import AsyncMock, Mock, patch

from middlewared.api.current import UpdateAvailableVersion
from middlewared.plugins.update_ import UpdateService
from middlewared.plugins.update_.trains import Release
from middlewared.pytest.unit.middleware import Middleware

release_manifest = {
    "version": "",
    "date": "",
    "changelog": "",
    "checksum": "",
    "filesize": 0,
    "profile": "",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("trains_releases,result", [
    (
        {
            "TrueNAS-SCALE-ElectricEel": {
                "24.10.0": {"filename": "24.10.0.update"},
                "24.10.1": {"filename": "24.10.1.update"},
                "24.10.2": {"filename": "24.10.2.update"},
            },
            "TrueNAS-SCALE-Fangtooth": {
                "25.04.0": {"filename": "25.04.0.update"},
                "25.04.1": {"filename": "25.04.1.update"},
            },
        },
        [
            UpdateAvailableVersion.model_validate({
                "train": "TrueNAS-SCALE-Fangtooth",
                "version": {
                    "version": "25.04.1",
                    "manifest": {**release_manifest,
                                 "train": "TrueNAS-SCALE-Fangtooth",
                                 "version": "25.04.1",
                                 "filename": "25.04.1.update"},
                    "release_notes": "Release notes for TrueNAS-SCALE-"
                                     "Fangtooth/25.04.1.update",
                    "release_notes_url": "https://truenas.com/25.04.1",
                },
            }),

            UpdateAvailableVersion.model_validate({
                "train": "TrueNAS-SCALE-Fangtooth",
                "version": {
                    "version": "25.04.0",
                    "manifest": {**release_manifest,
                                 "train": "TrueNAS-SCALE-Fangtooth",
                                 "version": "25.04.0",
                                 "filename": "25.04.0.update"},
                    "release_notes": "Release notes for TrueNAS-SCALE-"
                                     "Fangtooth/25.04.0.update",
                    "release_notes_url": "https://truenas.com/25.04.0"
                },
            }),

            UpdateAvailableVersion.model_validate({
                "train": "TrueNAS-SCALE-ElectricEel",
                "version": {
                    "version": "24.10.2",
                    "manifest": {**release_manifest,
                                 "train": "TrueNAS-SCALE-ElectricEel",
                                 "version": "24.10.2",
                                 "filename": "24.10.2.update"},
                    "release_notes": "Release notes for TrueNAS-SCALE-"
                                     "ElectricEel/24.10.2.update",
                    "release_notes_url": "https://truenas.com/24.10.2",
                },
            }),
        ]
    ),
])
async def test_update_available_versions(trains_releases, result):
    middleware = Middleware()
    middleware["network.general.will_perform_activity"] = Mock()
    middleware["system.release_notes_url"] = Mock(side_effect=lambda version: f"https://truenas.com/{version}")
    middleware["system.version_short"] = Mock(return_value="24.10.1")

    service = UpdateService(middleware)

    with patch('middlewared.plugins.update_.version.get_trains', AsyncMock()), \
         patch('middlewared.plugins.update_.version.get_next_trains_names',
               AsyncMock(return_value=list(reversed(trains_releases.keys())))), \
         patch('middlewared.plugins.update_.version.get_train_releases',
               AsyncMock(side_effect=lambda ctx, train: {
                   k: Release(**release_manifest, **v) for k, v in trains_releases[train].items()
               })), \
         patch('middlewared.plugins.update_.version.release_notes', AsyncMock(
             side_effect=lambda ctx, train, filename: f"Release notes for {train}/{filename}"
         )):
        assert await service.available_versions() == result
