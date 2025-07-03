import pytest
from unittest.mock import Mock

from middlewared.plugins.update_.profile_ import UpdateService as ProfileService
from middlewared.plugins.update_.status import UpdateService
from middlewared.plugins.update_.version import UpdateService as VersionUpdateService
from middlewared.pytest.unit.middleware import Middleware

CURRENT_CONFIG = {"profile": "CONSERVATIVE"}
CURRENT_VERSION = "25.04.1"
CURRENT_TRAIN_NAME = "TrueNAS-SCALE-Fangtooth"
CURRENT_VERSION_PROFILE = "CONSERVATIVE"
NEXT_TRAIN_NAMES = ["TrueNAS-SCALE-Goldfish", "TrueNAS-SCALE-Fangtooth"]


@pytest.mark.asyncio
@pytest.mark.parametrize("train_releases,result", [
    # Stay on current train
    (
        {
            "TrueNAS-SCALE-Fangtooth": {
                "25.04.1": {"profile": "MISSION_CRITICAL"},
                "25.04.2": {"profile": "CONSERVATIVE"},
            },
            "TrueNAS-SCALE-Goldfish": {
                "25.10.0": {"profile": "GENERAL"},
            },
        },
        {
            "code": "NORMAL",
            "error": None,
            "status": {
                "current_version": {
                    "train": "TrueNAS-SCALE-Fangtooth",
                    "profile": "CONSERVATIVE",
                    "matches_profile": True,
                },
                "new_version": {
                    "train": "TrueNAS-SCALE-Fangtooth",
                    "version": "25.04.2",
                    "profile": "CONSERVATIVE",
                },
            },
            "update_download_progress": None,
        },
    ),
    # Switch to next train
    (
        {
            "TrueNAS-SCALE-Fangtooth": {
                "25.04.1": {"profile": "MISSION_CRITICAL"},
                "25.04.2": {"profile": "CONSERVATIVE"},
            },
            "TrueNAS-SCALE-Goldfish": {
                "25.10.0": {"profile": "CONSERVATIVE"},
                "25.10.1": {"profile": "GENERAL"},
            },
        },
        {
            "code": "NORMAL",
            "error": None,
            "status": {
                "current_version": {
                    "train": "TrueNAS-SCALE-Fangtooth",
                    "profile": "CONSERVATIVE",
                    "matches_profile": True,
                },
                "new_version": {
                    "train": "TrueNAS-SCALE-Goldfish",
                    "version": "25.10.0",
                    "profile": "CONSERVATIVE",
                },
            },
            "update_download_progress": None,
        },
    ),
    # Current version is the latest
    (
        {
            "TrueNAS-SCALE-Fangtooth": {
                "25.04.1": {"profile": "MISSION_CRITICAL"},
                "25.04.2": {"profile": "GENERAL"},
            },
            "TrueNAS-SCALE-Goldfish": {
                "25.10.0": {"profile": "GENERAL"},
            },
        },
        {
            "code": "NORMAL",
            "error": None,
            "status": {
                "current_version": {
                    "train": "TrueNAS-SCALE-Fangtooth",
                    "profile": "CONSERVATIVE",
                    "matches_profile": True,
                },
                "new_version": None,
            },
            "update_download_progress": None,
        },
    ),
    # Removed version
    (
        {
            "TrueNAS-SCALE-Fangtooth": {
                "25.04.0": {"profile": "CONSERVATIVE"},
            },
            "TrueNAS-SCALE-Goldfish": {
                "25.10.0": {"profile": "GENERAL"},
            },
        },
        {
            "code": "ERROR",
            "error": (
                "Currently installed version 25.04.1 is newer than the newest version 25.04.0 provided by train "
                "TrueNAS-SCALE-Fangtooth."
            ),
            "status": None,
            "update_download_progress": None,
        },
    ),
])
async def test_update_status(train_releases, result):
    middleware = Middleware()
    middleware["cache.get"] = Mock(return_value=False)
    middleware["failover.licensed"] = Mock(return_value=False)
    middleware["system.version_short"] = Mock(return_value=CURRENT_VERSION)
    middleware["update.config"] = Mock(return_value=CURRENT_CONFIG)
    middleware["update.get_trains"] = Mock()
    middleware["update.get_current_train_name"] = Mock(return_value=CURRENT_TRAIN_NAME)
    middleware["update.current_version_profile"] = Mock(return_value=CURRENT_VERSION_PROFILE)
    middleware["update.profile_matches"] = Mock(side_effect=ProfileService(middleware).profile_matches)
    middleware["update.get_next_trains_names"] = Mock(return_value=NEXT_TRAIN_NAMES)
    middleware["update.get_train_releases"] = Mock(side_effect=lambda train: train_releases[train])
    middleware["update.version_from_manifest"] = Mock(side_effect=lambda v: v)
    middleware["update.can_update_to"] = Mock(side_effect=VersionUpdateService(middleware).can_update_to)
    service = UpdateService(middleware)

    assert await service.status() == result
