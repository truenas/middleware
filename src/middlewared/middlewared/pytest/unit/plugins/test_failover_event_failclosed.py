from unittest.mock import Mock, patch

from middlewared.plugins.failover_.event import FailoverEventsService
from middlewared.pytest.unit.middleware import Middleware


# fobj['volumes'] carries name/guid/status. NOTE the 'OFFLINE' status below: it is
# what pool.query reports for a pool it could not read (the spurious-OFFLINE that
# motivated this guard). The fail-closed check must IGNORE that and rely on the
# authoritative /proc kstat (query_imported_fast_impl) instead.
TANK_VOLUMES = [{"name": "tank", "guid": "123", "status": "OFFLINE"}]

# query_imported_fast_impl() shape: {guid: {'name': ..., 'state': ...}}
IMPORTED_WITH_TANK = {
    "123": {"name": "tank", "state": "ONLINE"},
    "999": {"name": "boot-pool", "state": "ONLINE"},
}
ONLY_BOOT_POOL = {"999": {"name": "boot-pool", "state": "ONLINE"}}

# query_imported_fast_impl is imported into the event module's namespace, so that
# is where we patch it.
QIF = "middlewared.plugins.failover_.event.query_imported_fast_impl"


def make_service():
    svc = FailoverEventsService(Middleware())
    # never actually sysrq-reboot the test runner
    svc.force_reboot = Mock()
    return svc


def test_demotion_reboots_when_pool_still_imported():
    # pool.query said OFFLINE (see volumes), but the authoritative kstat shows tank
    # is STILL imported -> must force-reboot instead of releasing fencing.
    svc = make_service()
    with patch(QIF, return_value=IMPORTED_WITH_TANK):
        svc.fence_if_pools_still_imported(TANK_VOLUMES)

    svc.force_reboot.assert_called_once()


def test_demotion_reboots_when_present_but_state_offline():
    # spa_state_to_name() can report OFFLINE/SUSPENDED while the pool is still
    # imported. We key on PRESENCE in the kstat namespace, not the state value, so
    # a still-present pool must force-reboot even when its state reads OFFLINE (the
    # spurious-OFFLINE failure mode that fooled the old status-gated export).
    imported = {"123": {"name": "tank", "state": "OFFLINE"}}
    svc = make_service()
    with patch(QIF, return_value=imported):
        svc.fence_if_pools_still_imported(TANK_VOLUMES)

    svc.force_reboot.assert_called_once()


def test_demotion_releases_when_pool_exported():
    # kstat shows only the boot pool -> tank really is exported -> safe, no reboot
    svc = make_service()
    with patch(QIF, return_value=ONLY_BOOT_POOL):
        svc.fence_if_pools_still_imported(TANK_VOLUMES)

    svc.force_reboot.assert_not_called()


def test_demotion_reboots_when_state_indeterminate():
    # cannot determine import state -> fail closed (force-reboot), never release
    svc = make_service()
    with patch(QIF, side_effect=RuntimeError("boom")):
        svc.fence_if_pools_still_imported(TANK_VOLUMES)

    svc.force_reboot.assert_called_once()


def test_demotion_ignores_boot_pools():
    # Each controller has its own boot pool that is ALWAYS imported. Neither valid
    # boot-pool name may count as still-attached data storage, otherwise we would
    # force-reboot on every demotion. tank is gone -> no reboot despite boot pools.
    imported = {
        "111": {"name": "boot-pool", "state": "ONLINE"},
        "222": {"name": "freenas-boot", "state": "ONLINE"},
    }
    svc = make_service()
    with patch(QIF, return_value=imported):
        svc.fence_if_pools_still_imported(TANK_VOLUMES)

    svc.force_reboot.assert_not_called()
