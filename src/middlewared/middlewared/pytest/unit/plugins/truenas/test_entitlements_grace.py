import asyncio
import logging
from unittest.mock import AsyncMock

import pytest

from middlewared.common.license_delegate import LicenseDelegate
from middlewared.plugins.truenas import entitlements_grace as grace
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ServiceContext
from middlewared.utils.entitlements import LicenseFeature

FC = LicenseFeature.FIBRECHANNEL
RDMA = LicenseFeature.RDMA
VMS = LicenseFeature.VMS


class _Delegate(LicenseDelegate):
    async def alert_lines(self, in_grace):
        return []


def _delegate(m, feature, services=()):
    delegate = _Delegate(m)
    delegate.feature = feature
    delegate.services = frozenset(services)
    delegate.on_grant = AsyncMock()
    return delegate


def _register(*delegates):
    registry = {}
    for delegate in delegates:
        grace.register(registry, delegate)
    return registry


def _take(tasks, name):
    found = [coro for coro in tasks if coro.cr_code.co_name == name]
    for coro in found:
        tasks.remove(coro)
    return found


@pytest.fixture
def env(monkeypatch):
    m = Middleware()
    store = {}
    running = set()
    tasks = []

    def cache_get(key):
        return store[key]

    def cache_put(key, value):
        store[key] = value

    m["cache.get"] = cache_get
    m["cache.put"] = cache_put
    m["failover.status"] = lambda: "MASTER"
    m["failover.sync_keys_to_remote_node"] = AsyncMock()
    m.services.service.started = lambda name: name in running
    m.services.alert.oneshot_create = AsyncMock()
    m.services.alert.oneshot_delete = AsyncMock()
    m.create_task = lambda coro, name=None: tasks.append(coro)
    monkeypatch.setattr(grace, "entitled_now", lambda: frozenset())

    context = ServiceContext(m, logging.getLogger("test_entitlements_grace"))
    yield context, m, store, running, tasks

    for coro in tasks:
        coro.close()


@pytest.mark.asyncio
async def test_license_changed_records_only_revoked_features_in_use(env):
    context, m, store, running, tasks = env
    fc, rdma, vms = _delegate(m, FC), _delegate(m, RDMA, {"nfs"}), _delegate(m, VMS)
    running.add("nfs")

    await grace.license_changed(
        context,
        _register(fc, rdma, vms),
        asyncio.Lock(),
        frozenset({FC, RDMA, VMS}),
        frozenset({FC}),
        True,
    )

    assert store[grace.GRACE_KEY] == [RDMA]
    m["failover.sync_keys_to_remote_node"].assert_awaited_once()
    for coro in _take(tasks, "_apply_grants"):
        await coro
    for delegate in (fc, rdma, vms):
        delegate.on_grant.assert_not_awaited()


@pytest.mark.asyncio
async def test_license_changed_grant_clears_record_and_runs_on_grant(env):
    context, m, store, running, tasks = env
    fc = _delegate(m, FC, {"iscsitarget"})
    store[grace.GRACE_KEY] = [FC]

    await grace.license_changed(context, _register(fc), asyncio.Lock(), frozenset(), frozenset({FC}), True)

    assert store[grace.GRACE_KEY] == []
    [apply_grants] = _take(tasks, "_apply_grants")
    await apply_grants
    fc.on_grant.assert_awaited_once()


@pytest.mark.asyncio
async def test_in_use_raising_keeps_feature_served(env):
    context, m, store, running, tasks = env
    fc, rdma = _delegate(m, FC), _delegate(m, RDMA)
    fc.in_use = AsyncMock(side_effect=RuntimeError("probe failed"))
    rdma.in_use = AsyncMock(return_value=True)

    await grace.license_changed(
        context,
        _register(fc, rdma),
        asyncio.Lock(),
        frozenset({FC, RDMA}),
        frozenset(),
        True,
    )

    assert store[grace.GRACE_KEY] == sorted([FC, RDMA])


@pytest.mark.asyncio
async def test_cut_service_removes_every_feature_listing_the_service(env):
    context, m, store, running, tasks = env
    fc = _delegate(m, FC, {"iscsitarget"})
    rdma = _delegate(m, RDMA, {"nfs", "iscsitarget", "nvmet", "nvmf"})
    vms = _delegate(m, VMS)
    store[grace.GRACE_KEY] = sorted([FC, RDMA, VMS])

    await grace.cut_service(context, _register(fc, rdma, vms), asyncio.Lock(), "nfs")

    assert store[grace.GRACE_KEY] == sorted([FC, VMS])
    m["failover.sync_keys_to_remote_node"].assert_not_awaited()
    assert [coro.cr_code.co_name for coro in tasks] == ["_push"]
