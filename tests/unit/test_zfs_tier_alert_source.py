"""Pure-logic unit tests for the zfs_tier alert source.

Mocks ``middleware.call_sync`` and the daemon's ``enum_jobs`` /
``get_info`` so the threshold math and OneShot create/delete flow can
be exercised without a real pool or daemon.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from middlewared.alert.source.zfs_tier import TierJobAlertSource
from middlewared.plugins.zfs.tier import special_vdev_thresholds


def _make_pool(name, *, usable, used):
    return {
        "name": name,
        "properties": {
            "class_special_usable": {"value": usable},
            "class_special_used": {"value": used},
        },
    }


def _make_middleware(
    *,
    enabled,
    pools=None,
    tier_map=None,
    max_used_percentage=80,
    special_class_metadata_reserve_pct=25,
):
    mw = MagicMock()
    mw.logger = MagicMock()
    calls = {"create": [], "delete": []}

    config = SimpleNamespace(
        enabled=enabled,
        max_used_percentage=max_used_percentage,
        special_class_metadata_reserve_pct=special_class_metadata_reserve_pct,
    )

    def call_sync(method, *args):
        if method == "zfs.tier.config":
            return config
        if method == "zpool.query_impl":
            return pools or []
        if method == "zfs.tier.bulk_get_tier_info":
            return tier_map or {}
        if method == "alert.oneshot_create":
            calls["create"].append((args[0], args[1]))
            return None
        if method == "alert.oneshot_delete":
            calls["delete"].append(args)
            return None
        raise AssertionError(f"unexpected middleware.call_sync({method!r}, ...)")

    mw.call_sync.side_effect = call_sync
    return mw, calls


def _make_source(mw):
    src = TierJobAlertSource.__new__(TierJobAlertSource)
    src.middleware = mw
    src._fired_terminal_jobs = set()
    src._fired_special_pools = set()
    return src


def test_check_sync_returns_empty_when_tiering_disabled():
    mw, calls = _make_middleware(enabled=False)
    src = _make_source(mw)
    assert src.check_sync() == []
    assert calls["create"] == []
    assert calls["delete"] == []


def test_check_sync_clears_state_on_disable():
    """Pre-seed in-memory state, then run with enabled=False — both sets
    are cleared and explicit oneshot_delete is issued for each."""
    mw, calls = _make_middleware(enabled=False)
    src = _make_source(mw)
    src._fired_special_pools = {"tank"}
    src._fired_terminal_jobs = {"tank/data@abc"}

    src.check_sync()
    assert src._fired_special_pools == set()
    assert src._fired_terminal_jobs == set()
    deletes = {(klass, key) for klass, key in calls["delete"]}
    assert ("TierSpecialVdevWarning", "tank") in deletes
    assert ("TierSpecialVdevCritical", "tank") in deletes
    assert ("TierJobError", "tank/data@abc") in deletes
    assert ("TierJobComplete", "tank/data@abc") in deletes


def _cfg(max_used_percentage, reserve_pct):
    return SimpleNamespace(
        max_used_percentage=max_used_percentage,
        special_class_metadata_reserve_pct=reserve_pct,
    )


def test_thresholds_default_config():
    """Default config (cap=80, reserve=25): physics-clamped to 75, warning 65."""
    assert special_vdev_thresholds(_cfg(80, 25)) == (65, 75)


def test_thresholds_cap_above_physics_clamps_to_physics():
    """Cap=95, reserve=25 → physics floor 75 wins. Cap value is meaningless above it."""
    assert special_vdev_thresholds(_cfg(95, 25)) == (65, 75)


def test_thresholds_cap_below_physics_uses_cap():
    """Cap=70, reserve=10 → physics ceiling 90, cap wins at 70."""
    assert special_vdev_thresholds(_cfg(70, 10)) == (60, 70)


def test_thresholds_raised_via_reserve_drop():
    """Cap=95, reserve=10 → both knobs lifted, critical 90."""
    assert special_vdev_thresholds(_cfg(95, 10)) == (80, 90)


def test_thresholds_warning_floor_is_50():
    """Hypothetical critical=55 would yield warning=45; floor clamps to 50."""
    assert special_vdev_thresholds(_cfg(55, 30)) == (50, 55)


@patch("middlewared.alert.source.zfs_tier.enum_jobs", return_value=iter([]))
def test_special_vdev_below_warning_fires_nothing_and_clears(_enum):
    mw, calls = _make_middleware(
        enabled=True,
        pools=[_make_pool("tank", usable=1000, used=600)],
    )
    src = _make_source(mw)
    src.check_sync()
    assert calls["create"] == []
    deletes = {(k, p) for k, p in calls["delete"]}
    assert ("TierSpecialVdevWarning", "tank") in deletes
    assert ("TierSpecialVdevCritical", "tank") in deletes


@patch("middlewared.alert.source.zfs_tier.enum_jobs", return_value=iter([]))
def test_special_vdev_warning_threshold(_enum):
    mw, calls = _make_middleware(
        enabled=True,
        pools=[_make_pool("tank", usable=1000, used=700)],
    )
    src = _make_source(mw)
    src.check_sync()

    assert len(calls["create"]) == 1
    klass, args = calls["create"][0]
    assert klass == "TierSpecialVdevWarning"
    assert args["pool_name"] == "tank"
    assert args["threshold"] == 65
    assert ("TierSpecialVdevCritical", "tank") in {(k, p) for k, p in calls["delete"]}


@patch("middlewared.alert.source.zfs_tier.enum_jobs", return_value=iter([]))
def test_special_vdev_critical_threshold(_enum):
    mw, calls = _make_middleware(
        enabled=True,
        pools=[_make_pool("tank", usable=1000, used=800)],
    )
    src = _make_source(mw)
    src.check_sync()

    assert len(calls["create"]) == 1
    klass, args = calls["create"][0]
    assert klass == "TierSpecialVdevCritical"
    assert args["pool_name"] == "tank"
    assert args["threshold"] == 75
    assert ("TierSpecialVdevWarning", "tank") in {(k, p) for k, p in calls["delete"]}


@patch("middlewared.alert.source.zfs_tier.enum_jobs", return_value=iter([]))
def test_special_vdev_raised_cap_shifts_thresholds(_enum):
    """With cap=95, reserve=10 the warning/critical lift to 80/90.
    85% used must fire WARNING, not CRITICAL."""
    mw, calls = _make_middleware(
        enabled=True,
        pools=[_make_pool("tank", usable=1000, used=850)],
        max_used_percentage=95,
        special_class_metadata_reserve_pct=10,
    )
    src = _make_source(mw)
    src.check_sync()

    creates = calls["create"]
    assert len(creates) == 1
    assert creates[0][0] == "TierSpecialVdevWarning"
    assert creates[0][1]["threshold"] == 80


@patch("middlewared.alert.source.zfs_tier.enum_jobs", return_value=iter([]))
def test_special_vdev_exactly_at_warning_threshold_does_not_fire(_enum):
    """``pct > warning`` is strictly greater. With cap=80, reserve=20 the
    warning lands at exactly 70; 70.0% used must not fire."""
    mw, calls = _make_middleware(
        enabled=True,
        pools=[_make_pool("tank", usable=1000, used=700)],
        max_used_percentage=80,
        special_class_metadata_reserve_pct=20,
    )
    src = _make_source(mw)
    src.check_sync()
    assert calls["create"] == []


@patch("middlewared.alert.source.zfs_tier.enum_jobs", return_value=iter([]))
def test_pool_without_special_vdev_is_skipped(_enum):
    """class_special_usable=0 means no SPECIAL vdev — no alert action."""
    mw, calls = _make_middleware(
        enabled=True,
        pools=[_make_pool("tank", usable=0, used=0)],
    )
    src = _make_source(mw)
    src.check_sync()
    assert calls["create"] == []
    assert calls["delete"] == []
    assert src._fired_special_pools == set()


@patch("middlewared.alert.source.zfs_tier.enum_jobs", return_value=iter([]))
def test_pool_that_disappeared_has_alerts_cleared(_enum):
    """A pool previously tracked but now absent should have its alerts
    deleted on the next poll."""
    mw, calls = _make_middleware(
        enabled=True,
        pools=[],
    )
    src = _make_source(mw)
    src._fired_special_pools = {"old_tank"}

    src.check_sync()
    deletes = {(k, p) for k, p in calls["delete"]}
    assert ("TierSpecialVdevWarning", "old_tank") in deletes
    assert ("TierSpecialVdevCritical", "old_tank") in deletes
    assert src._fired_special_pools == set()


def _job(dataset_name, job_uuid, status):
    return SimpleNamespace(
        dataset_name=dataset_name,
        job_uuid=job_uuid,
        status=status,
    )


@patch("middlewared.alert.source.zfs_tier.get_info")
@patch("middlewared.alert.source.zfs_tier.enum_jobs")
def test_error_job_fires_oneshot_once(mock_enum_jobs, mock_get_info):
    from truenas_zfstierd_common import RewriteJobStatus

    mock_enum_jobs.return_value = iter(
        [_job("tank/data", "abc", RewriteJobStatus.ERROR)]
    )
    mock_get_info.return_value = SimpleNamespace(error="permission denied", stats=None)

    mw, calls = _make_middleware(enabled=True, pools=[])
    src = _make_source(mw)
    src.check_sync()

    errors = [c for c in calls["create"] if c[0] == "TierJobError"]
    assert len(errors) == 1
    assert errors[0][1]["tier_job_id"] == "tank/data@abc"
    assert errors[0][1]["error"] == "permission denied"
    assert "tank/data@abc" in src._fired_terminal_jobs

    mock_enum_jobs.return_value = iter(
        [_job("tank/data", "abc", RewriteJobStatus.ERROR)]
    )
    calls["create"].clear()
    src.check_sync()
    assert [c for c in calls["create"] if c[0] == "TierJobError"] == []


@patch("middlewared.alert.source.zfs_tier.get_info")
@patch("middlewared.alert.source.zfs_tier.enum_jobs")
def test_complete_job_fires_oneshot_once(mock_enum_jobs, mock_get_info):
    from truenas_zfstierd_common import RewriteJobStatus

    mock_enum_jobs.return_value = iter(
        [_job("tank/data", "abc", RewriteJobStatus.COMPLETE)]
    )
    mock_get_info.return_value = SimpleNamespace(
        error=None,
        stats=SimpleNamespace(success=42, count_bytes=1024),
    )

    mw, calls = _make_middleware(
        enabled=True,
        pools=[],
        tier_map={"tank/data": {"tier_type": "PERFORMANCE", "tier_job": None}},
    )
    src = _make_source(mw)
    src.check_sync()

    completes = [c for c in calls["create"] if c[0] == "TierJobComplete"]
    assert len(completes) == 1
    assert completes[0][1]["tier_job_id"] == "tank/data@abc"
    assert completes[0][1]["files"] == 42
    assert completes[0][1]["tier"] == "PERFORMANCE"
    assert completes[0][1]["size"] == "1024"
    assert "tank/data@abc" in src._fired_terminal_jobs


@patch("middlewared.alert.source.zfs_tier.get_info")
@patch("middlewared.alert.source.zfs_tier.enum_jobs")
def test_job_leaving_error_state_clears_alert(mock_enum_jobs, mock_get_info):
    """ERROR job that's been recovered (now RUNNING) drops the alert."""
    from truenas_zfstierd_common import RewriteJobStatus

    mock_enum_jobs.return_value = iter(
        [_job("tank/data", "abc", RewriteJobStatus.ERROR)]
    )
    mock_get_info.return_value = SimpleNamespace(error="boom", stats=None)
    mw, calls = _make_middleware(enabled=True, pools=[])
    src = _make_source(mw)
    src.check_sync()
    assert "tank/data@abc" in src._fired_terminal_jobs

    mock_enum_jobs.return_value = iter(
        [_job("tank/data", "abc", RewriteJobStatus.RUNNING)]
    )
    calls["delete"].clear()
    src.check_sync()
    assert "tank/data@abc" not in src._fired_terminal_jobs
    deletes = {(k, p) for k, p in calls["delete"]}
    assert ("TierJobError", "tank/data@abc") in deletes
    assert ("TierJobComplete", "tank/data@abc") in deletes


@patch("middlewared.alert.source.zfs_tier.get_info")
@patch("middlewared.alert.source.zfs_tier.enum_jobs")
def test_job_disappearing_from_enum_drops_tracking(mock_enum_jobs, mock_get_info):
    """When a terminal job vanishes from enum_jobs (LMDB purge), the
    in-memory set drops it so a future re-creation would re-fire."""
    from truenas_zfstierd_common import RewriteJobStatus

    mock_enum_jobs.return_value = iter(
        [_job("tank/data", "abc", RewriteJobStatus.ERROR)]
    )
    mock_get_info.return_value = SimpleNamespace(error="boom", stats=None)
    mw, _ = _make_middleware(enabled=True, pools=[])
    src = _make_source(mw)
    src.check_sync()
    assert "tank/data@abc" in src._fired_terminal_jobs

    mock_enum_jobs.return_value = iter([])
    src.check_sync()
    assert "tank/data@abc" not in src._fired_terminal_jobs


@patch(
    "middlewared.alert.source.zfs_tier.enum_jobs", side_effect=Exception("daemon down")
)
def test_job_check_failure_doesnt_block_special_vdev_check(_enum):
    mw, calls = _make_middleware(
        enabled=True,
        pools=[_make_pool("tank", usable=1000, used=850)],
    )
    src = _make_source(mw)
    src.check_sync()
    crits = [c for c in calls["create"] if c[0] == "TierSpecialVdevCritical"]
    assert len(crits) == 1
