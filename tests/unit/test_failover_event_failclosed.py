from unittest.mock import Mock

from middlewared.plugins.failover_.event import FailoverEventsService
from middlewared.pytest.unit.middleware import Middleware


# fobj['volumes'] carries name/guid/status. NOTE the 'OFFLINE' status below: it is
# what pool.query reports for a pool it could not read (the spurious-OFFLINE that
# motivated this guard). The fail-closed check must IGNORE that and rely on the
# authoritative /proc kstat (zfs.pool.query_imported_fast) instead.
TANK_VOLUMES = [{'name': 'tank', 'guid': '123', 'status': 'OFFLINE'}]

# zfs.pool.query_imported_fast() shape: {guid: {'name': ..., 'state': ...}}
IMPORTED_WITH_TANK = {
    '123': {'name': 'tank', 'state': 'ONLINE'},
    '999': {'name': 'boot-pool', 'state': 'ONLINE'},
}
ONLY_BOOT_POOL = {'999': {'name': 'boot-pool', 'state': 'ONLINE'}}


def make_service(**method_mocks):
    m = Middleware()
    for name, mock in method_mocks.items():
        m[name.replace('__', '.')] = mock
    svc = FailoverEventsService(m)
    # never actually sysrq-reboot the test runner
    svc.self_fence = Mock()
    return svc


def test_demotion_self_fences_when_pool_still_imported():
    # pool.query said OFFLINE (see volumes), but the authoritative kstat shows tank
    # is STILL imported -> must self-fence instead of releasing fencing.
    svc = make_service(zfs__pool__query_imported_fast=Mock(return_value=IMPORTED_WITH_TANK))

    svc.fence_if_pools_still_imported(TANK_VOLUMES)

    svc.self_fence.assert_called_once()


def test_demotion_self_fences_when_present_but_state_offline():
    # spa_state_to_name() can report OFFLINE/SUSPENDED while the pool is still
    # imported. We key on PRESENCE in the kstat namespace, not the state value, so
    # a still-present pool must self-fence even when its state reads OFFLINE (the
    # spurious-OFFLINE failure mode that fooled the old status-gated export).
    imported = {'123': {'name': 'tank', 'state': 'OFFLINE'}}
    svc = make_service(zfs__pool__query_imported_fast=Mock(return_value=imported))

    svc.fence_if_pools_still_imported(TANK_VOLUMES)

    svc.self_fence.assert_called_once()


def test_demotion_releases_when_pool_exported():
    # kstat shows only the boot pool -> tank really is exported -> safe, no fence
    svc = make_service(zfs__pool__query_imported_fast=Mock(return_value=ONLY_BOOT_POOL))

    svc.fence_if_pools_still_imported(TANK_VOLUMES)

    svc.self_fence.assert_not_called()


def test_demotion_self_fences_when_state_indeterminate():
    # cannot determine import state -> fail closed (self-fence), never release
    svc = make_service(zfs__pool__query_imported_fast=Mock(side_effect=RuntimeError('boom')))

    svc.fence_if_pools_still_imported(TANK_VOLUMES)

    svc.self_fence.assert_called_once()


def test_demotion_ignores_boot_pools():
    # Each controller has its own boot pool that is ALWAYS imported. Neither valid
    # boot-pool name may count as still-attached data storage, otherwise we would
    # self-fence on every demotion. tank is gone -> no fence despite boot pools.
    imported = {
        '111': {'name': 'boot-pool', 'state': 'ONLINE'},
        '222': {'name': 'freenas-boot', 'state': 'ONLINE'},
    }
    svc = make_service(zfs__pool__query_imported_fast=Mock(return_value=imported))

    svc.fence_if_pools_still_imported(TANK_VOLUMES)

    svc.self_fence.assert_not_called()
