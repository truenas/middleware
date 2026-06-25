from unittest.mock import patch

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

# Both are imported into the event module's namespace, so that is where we patch
# them. Patching stcnith_reboot also keeps the test runner from actually rebooting.
QIF = "middlewared.plugins.failover_.event.query_imported_fast_impl"
SR = "middlewared.plugins.failover_.event.stcnith_reboot"


def make_service():
    return FailoverEventsService(Middleware())


def test_demotion_reboots_when_pool_still_imported():
    # pool.query said OFFLINE (see volumes), but the authoritative kstat shows tank
    # is STILL imported -> must force-reboot instead of releasing fencing.
    svc = make_service()
    with patch(QIF, return_value=IMPORTED_WITH_TANK), patch(SR) as reboot:
        svc.fence_if_pools_still_imported(TANK_VOLUMES)

    reboot.assert_called_once()


def test_demotion_reboots_when_present_but_state_offline():
    # spa_state_to_name() can report OFFLINE/SUSPENDED while the pool is still
    # imported. We key on PRESENCE in the kstat namespace, not the state value, so
    # a still-present pool must force-reboot even when its state reads OFFLINE (the
    # spurious-OFFLINE failure mode that fooled the old status-gated export).
    imported = {"123": {"name": "tank", "state": "OFFLINE"}}
    svc = make_service()
    with patch(QIF, return_value=imported), patch(SR) as reboot:
        svc.fence_if_pools_still_imported(TANK_VOLUMES)

    reboot.assert_called_once()


def test_demotion_releases_when_pool_exported():
    # kstat shows only the boot pool -> tank really is exported -> safe, no reboot
    svc = make_service()
    with patch(QIF, return_value=ONLY_BOOT_POOL), patch(SR) as reboot:
        svc.fence_if_pools_still_imported(TANK_VOLUMES)

    reboot.assert_not_called()


def test_demotion_reboots_when_state_indeterminate():
    # cannot determine import state -> fail closed (force-reboot), never release
    svc = make_service()
    with patch(QIF, side_effect=RuntimeError("boom")), patch(SR) as reboot:
        svc.fence_if_pools_still_imported(TANK_VOLUMES)

    reboot.assert_called_once()


def test_demotion_ignores_boot_pools():
    # Each controller has its own boot pool that is ALWAYS imported. Neither valid
    # boot-pool name may count as still-attached data storage, otherwise we would
    # force-reboot on every demotion. tank is gone -> no reboot despite boot pools.
    imported = {
        "111": {"name": "boot-pool", "state": "ONLINE"},
        "222": {"name": "freenas-boot", "state": "ONLINE"},
    }
    svc = make_service()
    with patch(QIF, return_value=imported), patch(SR) as reboot:
        svc.fence_if_pools_still_imported(TANK_VOLUMES)

    reboot.assert_not_called()
