import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.truesearch import TrueSearchService
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware

BOOT_POOL_REASON = "The system dataset must not reside on the boot pool."
# The unlicensed wording, so the denial columns below must be the ones with no license at
# all. A licensed-without-the-key column reports a different sentence.
NOT_LICENSED = "This system is not licensed to use the TrueSearch feature."


@pytest.mark.asyncio
@pytest.mark.parametrize("directories,datasets,result", [
    ({"/mnt/tank/users"}, {"tank": False}, ["/mnt/tank/users"]),
    ({"/mnt/tank/users/alex"}, {"tank": False, "tank/users": False}, ["/mnt/tank/users/alex"]),
    ({"/mnt/tank/users"}, {"tank": False, "tank/users": True}, []),
    ({"/mnt/tank/users/alex"}, {"tank": False, "tank/users": True}, []),
    ({"/mnt/tank/users"},
     {"tank": False, "tank/users": False, "tank/users/alice": False, "tank/users/bob": False,
      "tank/users/alice/books": False, "tank/users/alice/documents": True},
     ["/mnt/tank/users", "/mnt/tank/users/alice", "/mnt/tank/users/alice/books", "/mnt/tank/users/bob"]),
])
async def test_process_directories(directories, datasets, result):
    middleware = Mock()
    middleware.call2 = AsyncMock(return_value=[
        {
            "type": "FILESYSTEM",
            "properties": {
                "mountpoint": {
                    "value": f"/mnt/{dataset}"
                },
                "encryption": {
                    "value": "on" if encrypted else "off"
                },
            }
        }
        for dataset, encrypted in datasets.items()
    ])
    assert await TrueSearchService(middleware).process_directories(directories) == result


@pytest.mark.asyncio
async def test_legacy_mountpoint():
    middleware = Mock()
    middleware.call2 = AsyncMock(return_value=[
        {
            "type": "FILESYSTEM",
            "properties": {
                "mountpoint": {
                    "value": "legacy"
                },
                "encryption": {
                    "value": "off"
                },
            }
        },
        {
            "type": "FILESYSTEM",
            "properties": {
                "mountpoint": {
                    "value": "/mnt/tank/users"
                },
                "encryption": {
                    "value": "off"
                },
            }
        },
    ])
    assert await TrueSearchService(middleware).process_directories({"/mnt/tank/users"}) == ["/mnt/tank/users"]


@pytest.mark.asyncio
async def test_unavailable_reasons_omits_licensing_reason_when_entitled():
    m = Middleware()
    m["systemdataset.is_boot_pool"] = lambda *args: False
    checked = install_entitlements_for_column(m, LicenseFeature.TRUESEARCH, "HW+K")

    assert await create_service(m, TrueSearchService).unavailable_reasons() == []
    assert checked == [LicenseFeature.TRUESEARCH]


@pytest.mark.asyncio
async def test_unavailable_reasons_reports_boot_pool_and_licensing_together():
    m = Middleware()
    m["systemdataset.is_boot_pool"] = lambda *args: True
    install_entitlements_for_column(m, LicenseFeature.TRUESEARCH, "CE")

    assert await create_service(m, TrueSearchService).unavailable_reasons() == [BOOT_POOL_REASON, NOT_LICENSED]


@pytest.fixture
def truesearch(monkeypatch):
    monkeypatch.setattr(TrueSearchService, "MOUNT_CHECK_DELAY", 0.01)
    m = Middleware()
    m.create_task = asyncio.create_task
    svc = TrueSearchService(m)
    svc.raw_directories = AsyncMock(return_value={"/mnt/tank/share"})
    svc.configure = AsyncMock()
    return svc


@pytest.mark.asyncio
async def test_burst_of_mounts_is_checked_once(truesearch):
    await truesearch.schedule_mount_check("/mnt/tank/share/ds0")
    first_timer = truesearch.mount_check_timer
    for i in range(1, 100):
        await truesearch.schedule_mount_check(f"/mnt/tank/share/ds{i}")
    # Each mount restarts the delay
    assert first_timer.cancelled()
    # The last timer was armed before this sleep with a shorter delay, so the check runs first
    await asyncio.sleep(0.1)
    truesearch.raw_directories.assert_awaited_once()
    truesearch.configure.assert_awaited_once()


@pytest.mark.asyncio
async def test_mount_during_a_check_is_checked_by_the_next_one(truesearch):
    later_mounts = ["/mnt/tank/share/child"]

    async def raw_directories():
        # Another dataset is mounted while the check looks up the directories
        if later_mounts:
            await truesearch.schedule_mount_check(later_mounts.pop())
        return {"/mnt/tank/share"}

    truesearch.raw_directories = raw_directories
    await truesearch.schedule_mount_check("/mnt/tank/other")
    # Run the checks the timers would run, one after the other, instead of waiting for them
    await truesearch.check_mounted_paths()
    truesearch.configure.assert_not_awaited()
    await truesearch.check_mounted_paths()
    truesearch.configure.assert_awaited_once()
    # Don't let the second mount's timer fire after the test
    truesearch.mount_check_timer.cancel()


@pytest.mark.asyncio
async def test_service_state_is_not_queried_when_search_is_off():
    m = Middleware()
    m["smb.config"] = Mock(return_value={"search_protocols": []})
    m.services.webshare.config = AsyncMock(return_value=Mock(search=False))
    m.services.service.started_or_enabled = AsyncMock(return_value=True)
    assert await TrueSearchService(m).raw_directories() == set()
    m.services.service.started_or_enabled.assert_not_awaited()
