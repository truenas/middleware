import pytest
from unittest.mock import Mock

from middlewared.api.current import UpdateStatus
from middlewared.plugins.update_.config import UpdateService
from middlewared.plugins.update_.trains import Release
from middlewared.pytest.unit.middleware import Middleware

CURRENT_CONFIG = Mock(profile="MISSION_CRITICAL")
CURRENT_VERSION = "25.04.1"
CURRENT_TRAIN_NAME = "TrueNAS-SCALE-Fangtooth"
CURRENT_VERSION_PROFILE = "MISSION_CRITICAL"
NEXT_TRAIN_NAMES = ["TrueNAS-SCALE-Goldfish", "TrueNAS-SCALE-Fangtooth"]

release_manifest = {
    "filename": "",
    "version": "",
    "date": "",
    "changelog": "",
    "checksum": "",
    "filesize": 0,
}
new_version_manifest = {
    "manifest": {**release_manifest, 'profile': 'MISSION_CRITICAL', 'train': 'TrueNAS-SCALE-Fangtooth'},
    "release_notes": "<release notes>",
    "release_notes_url": "<release notes url>",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("train_releases,result", [
    # Stay on current train
    (
        {
            "TrueNAS-SCALE-Fangtooth": {
                "25.04.1": Release(**release_manifest, profile="MISSION_CRITICAL"),
                "25.04.2": Release(**release_manifest, profile="MISSION_CRITICAL"),
            },
            "TrueNAS-SCALE-Goldfish": {
                "25.10.0": Release(**release_manifest, profile="GENERAL"),
            },
        },
        UpdateStatus.model_validate({
            "code": "NORMAL",
            "error": None,
            "status": {
                "current_version": {
                    "train": "TrueNAS-SCALE-Fangtooth",
                    "profile": "MISSION_CRITICAL",
                    "matches_profile": True,
                },
                "new_version": {
                    **new_version_manifest,
                    "version": "25.04.2",
                    "manifest": {
                        **release_manifest,
                        "train": "TrueNAS-SCALE-Fangtooth",
                        "version": "25.04.2",
                        "profile": "MISSION_CRITICAL",
                    },
                },
            },
            "update_download_progress": None,
        }),
    ),
    # Switch to next train
    (
        {
            "TrueNAS-SCALE-Fangtooth": {
                "25.04.1": Release(**release_manifest, profile="MISSION_CRITICAL"),
                "25.04.2": Release(**release_manifest, profile="MISSION_CRITICAL"),
            },
            "TrueNAS-SCALE-Goldfish": {
                "25.10.0": Release(**release_manifest, profile="MISSION_CRITICAL"),
                "25.10.1": Release(**release_manifest, profile="GENERAL"),
            },
        },
        UpdateStatus.model_validate({
            "code": "NORMAL",
            "error": None,
            "status": {
                "current_version": {
                    "train": "TrueNAS-SCALE-Fangtooth",
                    "profile": "MISSION_CRITICAL",
                    "matches_profile": True,
                },
                "new_version": {
                    **new_version_manifest,
                    "version": "25.10.0",
                    "manifest": {
                        **release_manifest,
                        "train": "TrueNAS-SCALE-Goldfish",
                        "version": "25.10.0",
                        "profile": "MISSION_CRITICAL",
                    },
                },
            },
            "update_download_progress": None,
        }),
    ),
    # Current version is the latest
    (
        {
            "TrueNAS-SCALE-Fangtooth": {
                "25.04.1": Release(**release_manifest, profile="MISSION_CRITICAL"),
                "25.04.2": Release(**release_manifest, profile="GENERAL"),
            },
            "TrueNAS-SCALE-Goldfish": {
                "25.10.0": Release(**release_manifest, profile="GENERAL"),
            },
        },
        UpdateStatus.model_validate({
            "code": "NORMAL",
            "error": None,
            "status": {
                "current_version": {
                    "train": "TrueNAS-SCALE-Fangtooth",
                    "profile": "MISSION_CRITICAL",
                    "matches_profile": True,
                },
                "new_version": None,
            },
            "update_download_progress": None,
        }),
    ),
    # Removed version
    (
        {
            "TrueNAS-SCALE-Fangtooth": {
                "25.04.0": Release(**release_manifest, profile="MISSION_CRITICAL"),
            },
            "TrueNAS-SCALE-Goldfish": {
                "25.10.0": Release(**release_manifest, profile="GENERAL"),
            },
        },
        UpdateStatus.model_validate({
            "code": "ERROR",
            "error": {
                "errname": "ENOPKG",
                "reason": (
                    "Currently installed version 25.04.1 is newer than the newest version 25.04.0 provided by train "
                    "TrueNAS-SCALE-Fangtooth."
                ),
            },
            "status": None,
            "update_download_progress": None,
        }),
    ),
])
async def test_update_status(train_releases, result):
    middleware = Middleware()
    middleware["cache.get"] = Mock(return_value=False)
    middleware["failover.licensed"] = Mock(return_value=False)
    middleware["system.release_notes_url"] = Mock(return_value="<release notes url>")
    middleware["system.version_short"] = Mock(return_value=CURRENT_VERSION)
    middleware.services.update.config = Mock(return_value=CURRENT_CONFIG)
    middleware.services.update.get_trains = Mock()
    middleware.services.update.get_current_train_name = Mock(return_value=CURRENT_TRAIN_NAME)
    middleware.services.update.current_version_profile = Mock(return_value=CURRENT_VERSION_PROFILE)
    middleware.services.update.profile_matches = Mock(side_effect=UpdateService(middleware).profile_matches)
    middleware.services.update.get_next_trains_names = Mock(return_value=NEXT_TRAIN_NAMES)
    middleware.services.update.get_train_releases = Mock(side_effect=lambda train: train_releases[train])
    middleware.services.update.release_notes = Mock(return_value="<release notes>")
    middleware.services.update.version_from_manifest = Mock(side_effect=UpdateService(middleware).version_from_manifest)
    middleware.services.update.can_update_to = Mock(side_effect=UpdateService(middleware).can_update_to)
    service = UpdateService(middleware)

    assert await service.status() == result
