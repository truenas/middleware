import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.plugins.truesearch import TrueSearchService, on_dataset_mounted
from middlewared.pytest.unit.middleware import Middleware


@pytest.fixture
def truesearch(monkeypatch):
    monkeypatch.setattr(TrueSearchService, "MOUNT_CHECK_DELAY", 0.01)
    m = Middleware()
    m.create_task = lambda coro, **kwargs: asyncio.get_running_loop().create_task(coro)
    svc = TrueSearchService(m)
    svc.logger = Mock()
    svc.raw_directories = AsyncMock(return_value={"/mnt/tank/share"})
    svc.schedule_reconfigure = AsyncMock()
    return svc


async def mount(svc, *paths):
    for path in paths:
        await svc.schedule_mount_check(path)
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_burst_of_mounts_is_checked_once(truesearch):
    await truesearch.schedule_mount_check("/mnt/tank/ds0")
    first_timer = truesearch.mount_check_timer
    await mount(truesearch, *[f"/mnt/tank/ds{i}" for i in range(1, 100)])
    # Each mount restarts the delay
    assert first_timer.cancelled()
    truesearch.raw_directories.assert_awaited_once()
    truesearch.schedule_reconfigure.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path, intersects",
    [
        ("/mnt/tank/share/child", True),
        ("/mnt/tank/share", True),
        ("/mnt/tank", True),
        ("/mnt/tank/shared", False),
        ("/mnt/tank2/share", False),
    ],
)
async def test_mount_intersecting_indexed_directory_schedules_reconfigure(truesearch, path, intersects):
    await mount(truesearch, "/mnt/tank/other", path)
    assert truesearch.schedule_reconfigure.await_count == int(intersects)


@pytest.mark.asyncio
async def test_mounts_after_a_check_are_checked_again(truesearch):
    await mount(truesearch, "/mnt/tank/other")
    await mount(truesearch, "/mnt/tank/share/child")
    assert truesearch.raw_directories.await_count == 2
    truesearch.schedule_reconfigure.assert_awaited_once()


@pytest.mark.asyncio
async def test_mount_during_a_check_is_checked_by_the_next_one(truesearch):
    looking_up = asyncio.Event()
    finish_lookup = asyncio.Event()

    async def raw_directories():
        looking_up.set()
        await finish_lookup.wait()
        return {"/mnt/tank/share"}

    truesearch.raw_directories.side_effect = raw_directories
    await truesearch.schedule_mount_check("/mnt/tank/other")
    await looking_up.wait()
    await truesearch.schedule_mount_check("/mnt/tank/share/child")
    finish_lookup.set()
    await asyncio.sleep(0.1)
    assert truesearch.raw_directories.await_count == 2
    truesearch.schedule_reconfigure.assert_awaited_once()


@pytest.mark.asyncio
async def test_mount_just_before_a_check_starts_is_checked_once(truesearch):
    # The timer has fired and its check is about to start when another mount arrives
    truesearch.mounted_paths.add("/mnt/tank/other")
    check = asyncio.get_running_loop().create_task(truesearch.check_mounted_paths())
    await truesearch.schedule_mount_check("/mnt/tank/share/child")
    timer = truesearch.mount_check_timer
    await check
    # The check must keep the timer that mount scheduled, so that later mounts can still restart its delay
    assert truesearch.mount_check_timer is timer
    await asyncio.sleep(0.1)
    truesearch.raw_directories.assert_awaited_once()
    truesearch.schedule_reconfigure.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_lookup_is_logged(truesearch):
    truesearch.raw_directories.side_effect = RuntimeError("boom")
    await mount(truesearch, "/mnt/tank/share/child")
    truesearch.schedule_reconfigure.assert_not_awaited()
    truesearch.logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_mount_hook_schedules_a_check():
    m = Middleware()
    m.services.truesearch.schedule_mount_check = AsyncMock()
    await on_dataset_mounted(m, {"mountpoint": "/mnt/tank/ds"})
    m.services.truesearch.schedule_mount_check.assert_awaited_once_with("/mnt/tank/ds")


@pytest.mark.asyncio
async def test_service_state_is_not_queried_when_search_is_off():
    m = Middleware()
    m["smb.config"] = Mock(return_value={"search_protocols": []})
    m.services.webshare.config = AsyncMock(return_value=Mock(search=False))
    m.services.service.started_or_enabled = AsyncMock(return_value=True)
    assert await TrueSearchService(m).raw_directories() == set()
    m.services.service.started_or_enabled.assert_not_awaited()
