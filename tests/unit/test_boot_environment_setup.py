"""Unit tests for the boot_environment plugin's setup() reconcile logic.

setup() runs at middlewared start: if the truenas:grub_pending marker is set
(a boot menu regeneration was interrupted by a crash), it regenerates the menu
under the mutation lock. On a real boot it also promotes the active BE's
installer-cloned datasets. These paths cannot be reached by the api2 integration
tests, so they are covered here with a mocked middleware.
"""

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# The plugin imports the truenas_bootenv engine at module load, and the engine
# imports the ZFS binding, so mock the truenas_bootenv modules to keep this test
# runnable without a ZFS kernel module. Deliberately NOT mocking truenas_pylibzfs
# itself: mocking the engine already stops it being imported, and other unit
# tests in this process import the real binding.
for _mod in (
    "truenas_bootenv",
    "truenas_bootenv.engine",
    "truenas_bootenv.naming",
    "truenas_bootenv.errors",
):
    sys.modules.setdefault(_mod, MagicMock())

from middlewared.plugins.boot_environment import setup  # noqa: E402


def _middleware(*, marker, system_ready=True):
    middleware = MagicMock()
    # setup() reaches the typed boot.environment methods through
    # middleware.call2(<bound method>, ...); MagicMock returns the same
    # child mock for repeated attribute access, so identity comparison
    # against these references is stable.
    be_service = middleware.services.boot.environment

    async def call(method, *args):
        if method == "system.ready":
            return system_ready
        return None

    async def call2(f, *args):
        if f is middleware.services.boot.pool_name:
            return "boot-pool"
        if f is be_service.be_grub_marker_impl:
            return marker
        return None

    middleware.call = AsyncMock(side_effect=call)
    middleware.call2 = AsyncMock(side_effect=call2)
    middleware.logger = MagicMock()
    return middleware


def _call2_calls(middleware):
    be_service = middleware.services.boot.environment
    names = {
        middleware.services.boot.pool_name: "pool_name",
        be_service.be_grub_marker_impl: "be_grub_marker_impl",
        be_service.regenerate_grub: "regenerate_grub",
        be_service.promote_current_datasets: "promote_current_datasets",
    }
    return [(names.get(c.args[0], c.args[0]), c.args[1:]) for c in middleware.call2.call_args_list]


def _call2_methods(middleware):
    return [name for name, _args in _call2_calls(middleware)]


@pytest.mark.asyncio
async def test_setup_regenerates_grub_when_marker_pending():
    middleware = _middleware(marker=True)
    await setup(middleware)
    calls = _call2_calls(middleware)
    # the marker is read for the right pool, and the recovery regeneration
    # runs non-fatally under the setup schema name
    assert ("be_grub_marker_impl", ("boot-pool", "get")) in calls
    assert ("regenerate_grub", ("setup", False)) in calls
    middleware.logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_setup_does_not_regenerate_when_no_marker():
    middleware = _middleware(marker=False)
    await setup(middleware)
    assert "regenerate_grub" not in _call2_methods(middleware)
    middleware.logger.warning.assert_not_called()


@pytest.mark.asyncio
async def test_setup_promotes_datasets_on_boot():
    middleware = _middleware(marker=False, system_ready=False)
    await setup(middleware)
    assert "promote_current_datasets" in _call2_methods(middleware)


@pytest.mark.asyncio
async def test_setup_skips_promotion_on_restart():
    middleware = _middleware(marker=False, system_ready=True)
    await setup(middleware)
    assert "promote_current_datasets" not in _call2_methods(middleware)
