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
async def test_get_disks_caches_and_clears():
    state = BootPoolState()
    state.set_name("boot-pool")
    middleware = MagicMock()
    middleware.call = AsyncMock(return_value={"disks": ["sda", "sdb"]})

    assert await state.get_disks(middleware) == ["sda", "sdb"]
    assert await state.get_disks(middleware) == ["sda", "sdb"]
    middleware.call.assert_called_once()  # second read is served from cache

    state.clear_disks_cache()
    await state.get_disks(middleware)
    assert middleware.call.call_count == 2  # cleared cache forces a refetch


@pytest.mark.asyncio
async def test_warm_disks_swallows_and_logs(caplog):
    state = BootPoolState()
    state.set_name("boot-pool")
    middleware = MagicMock()
    middleware.call = AsyncMock(side_effect=RuntimeError("boom"))

    await state._warm_disks(middleware)  # must not raise

    assert "failed to warm boot-pool disk cache" in caplog.text


@pytest.mark.asyncio
async def test_initialize_raises_when_no_known_pool(monkeypatch):
    async def fake_run(*args, **kwargs):
        return MagicMock(stdout="tank\toff\n")

    monkeypatch.setattr(pool_mod, "run", fake_run)

    with pytest.raises(BootPoolNotDetected):
        await BootPoolState().initialize(MagicMock())


@pytest.mark.asyncio
async def test_initialize_detects_and_schedules_warm(monkeypatch):
    async def fake_run(*args, **kwargs):
        return MagicMock(stdout="boot-pool\tgrub2\n")

    monkeypatch.setattr(pool_mod, "run", fake_run)
    state = BootPoolState()
    middleware = MagicMock()

    await state.initialize(middleware)

    assert state.get_name() == "boot-pool"
    middleware.create_task.assert_called_once()
    # The scheduled coroutine is never awaited in this test; close it to avoid a warning.
    middleware.create_task.call_args.args[0].close()
