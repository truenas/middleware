from unittest.mock import AsyncMock, MagicMock

import pytest

from middlewared.utils.boot import pool as pool_mod
from middlewared.utils.boot.pool import BootPoolNotDetected, BootPoolState


def test_get_name_raises_before_detection():
    with pytest.raises(BootPoolNotDetected):
        BootPoolState().get_name()


def test_get_name_returns_after_set():
    state = BootPoolState()
    state.set_name("boot-pool")
    assert state.get_name() == "boot-pool"


@pytest.mark.asyncio
async def test_get_disks_uses_cache():
    state = BootPoolState()
    state.set_name("boot-pool")
    middleware = MagicMock()
    middleware.call = AsyncMock(return_value={"disks": ["sda", "sdb"]})

    assert await state.get_disks(middleware) == ["sda", "sdb"]
    assert await state.get_disks(middleware) == ["sda", "sdb"]
    middleware.call.assert_called_once()  # second read is served from cache


@pytest.mark.asyncio
async def test_get_disks_use_cache_false_refetches_and_refills():
    state = BootPoolState()
    state.set_name("boot-pool")
    middleware = MagicMock()
    middleware.call = AsyncMock(return_value={"disks": ["sda", "sdb"]})
    await state.get_disks(middleware)  # fill cache

    middleware.call = AsyncMock(return_value={"disks": ["sda", "sdb", "sdc"]})
    result = await state.get_disks(middleware, use_cache=False)

    assert result == ["sda", "sdb", "sdc"]  # live value returned
    middleware.call.assert_called_once()  # bypassed the cache and refetched
    assert await state.get_disks(middleware) == ["sda", "sdb", "sdc"]  # cache refilled with the new value


@pytest.mark.asyncio
async def test_initialize_raises_when_no_known_pool(monkeypatch):
    async def fake_run(*args, **kwargs):
        return MagicMock(stdout="tank\toff\n")

    monkeypatch.setattr(pool_mod, "run", fake_run)

    with pytest.raises(BootPoolNotDetected):
        await BootPoolState().initialize(MagicMock())


@pytest.mark.asyncio
async def test_initialize_detects_and_fills_cache(monkeypatch):
    async def fake_run(*args, **kwargs):
        return MagicMock(stdout="boot-pool\tgrub2\n")

    monkeypatch.setattr(pool_mod, "run", fake_run)
    state = BootPoolState()
    middleware = MagicMock()
    middleware.call = AsyncMock(return_value={"disks": ["sda", "sdv"]})

    await state.initialize(middleware)

    assert state.get_name() == "boot-pool"
    assert await state.get_disks(middleware) == ["sda", "sdv"]  # cache was filled during initialize
    middleware.call.assert_called_once()  # get_disks hit zpool.status exactly once (via initialize)
