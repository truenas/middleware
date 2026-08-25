"""
All job-alert assertions are scoped to this module's own dataset names:
rewrite-job records live in LMDB under ``/var/db/system/truenas_zfstierd``,
survive dataset deletion and pool export, and therefore accumulate across
tests and suite runs.
"""

import time

import pytest

from middlewared.test.integration.utils import call, ssh

# Written by the tier_pool conftest fixture context; used by tests that stage
# data through the SPECIAL vdev.
SEED = "/dev/shm/tier_alert_seed"

# Daemon test hook shared with conftest.py: per-file rewrite delay in ms.
SLOW_REWRITE_SENTINEL = "/var/run/truenas_zfstierd/slow_rewrite"

# Direct daemon job creation, bypassing the middleware validation that
# (correctly) refuses to create a rewrite job on a read-only dataset. The
# daemon itself does not check readonly, so the job starts and its walker
# fails with EROFS on the first file — a deterministic ERROR-state job.
_DAEMON_CREATE_JOB = """\
import asyncio
from truenas_zfstierd_client import RewriteClient

async def main():
    client = RewriteClient()
    await client.connect()
    try:
        result = await client.create_job({ds!r})
    finally:
        await client.close()
    print(result.job_uuid)

asyncio.run(main())
"""


@pytest.fixture(scope="module", autouse=True)
def clean_job_db(tier_pool):
    """Start this module with an empty rewrite-job database.

    Job records survive dataset deletion and pool destruction, so without
    this, records left by earlier suite runs would appear in every
    ``alert.run_source`` result. The daemon recreates the state directory
    on start."""
    ssh(
        "systemctl stop truenas_zfstierd && "
        "rm -rf /var/db/system/truenas_zfstierd/* && "
        "systemctl start truenas_zfstierd"
    )


def _run_source():
    return call("alert.run_source", "TierJob")


def _job_alerts_for(ds_name):
    return [alert for alert in _run_source() if alert["args"].get("tier_job_id", "").startswith(f"{ds_name}@")]


def _special_vdev_alerts_for(pool_name):
    return [
        alert
        for alert in _run_source()
        if alert["klass"].startswith("TierSpecialVdev") and alert["args"].get("pool_name") == pool_name
    ]


def _stage_rewrite_work(ds_name, files=5, size_mb=1):
    """PERFORMANCE -> write -> REGULAR: every block now sits on SPECIAL but
    belongs on NORMAL, so a rewrite job has real per-file work to do."""
    call("zfs.tier.dataset_set_tier", {"dataset_name": ds_name, "tier_type": "PERFORMANCE"})
    ssh(f"cd /mnt/{ds_name} && seq 1 {files} | xargs -I X dd if=/dev/urandom of=fX bs=1M count={size_mb} 2>/dev/null")
    call("zfs.tier.dataset_set_tier", {"dataset_name": ds_name, "tier_type": "REGULAR"})


def _complete_job(ds_name, wait_for_job_status, files=5):
    _stage_rewrite_work(ds_name, files=files)
    entry = call("zfs.tier.rewrite_job_create", {"dataset_name": ds_name})
    status = wait_for_job_status(entry["tier_job_id"], {"COMPLETE", "ERROR"}, timeout=120)
    assert status == "COMPLETE"
    return entry["tier_job_id"]


def _special_vdev_pct(pool_name):
    for pool in call(
        "zpool.query_impl",
        {"properties": ["class_special_usable", "class_special_used"]},
    ):
        if pool["name"] == pool_name:
            props = pool["properties"]
            return 100 * props["class_special_used"]["value"] / props["class_special_usable"]["value"]
    raise AssertionError(f"pool {pool_name!r} not found")


# ----------------------------------------------------------------------------
# Gate: tiering disabled -> the source reports nothing at all.
# ----------------------------------------------------------------------------


def test_disabled_tiering_produces_no_alerts(tier_pool, disabled_tier):
    assert _run_source() == []


# ----------------------------------------------------------------------------
# COMPLETE job -> NOTICE alert with migration stats.
# ----------------------------------------------------------------------------


def test_complete_job_raises_notice_alert(tier_ds, wait_for_job_status):
    # The module starts with an empty job database, so the first enabled poll
    # sees no terminal jobs at all.
    assert [a for a in _run_source() if a["klass"].startswith("TierJob")] == []

    tier_job_id = _complete_job(tier_ds, wait_for_job_status, files=5)

    alerts = _job_alerts_for(tier_ds)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["klass"] == "TierJobComplete"
    assert alert["args"] == {
        "tier_job_id": tier_job_id,
        "files": 5,
        "tier": "REGULAR",
        "size": str(5 * 1024 * 1024),
    }

    # A second poll with an unchanged terminal-job set serves the same alert
    # (from the source's cache — equal output either way).
    assert _job_alerts_for(tier_ds) == alerts


# ----------------------------------------------------------------------------
# A job that is still running is not a terminal state -> no alert.
# ----------------------------------------------------------------------------


def test_running_job_raises_no_alert(tier_ds_with_work, wait_for_job_status):
    entry = call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds_with_work})
    wait_for_job_status(entry["tier_job_id"], {"QUEUED", "RUNNING"}, timeout=30)

    alerts = _job_alerts_for(tier_ds_with_work)

    # Guard against the job having completed under the alert query: the
    # slow-rewrite sentinel gives it a >=20s lifetime, so it must still be
    # active — which makes the empty-alerts assertion meaningful.
    status = call("zfs.tier.rewrite_job_status", {"tier_job_id": entry["tier_job_id"]})
    assert status["status"] in ("QUEUED", "RUNNING")
    assert alerts == []


# ----------------------------------------------------------------------------
# ERROR job -> CRITICAL alert carrying the daemon's error text.
# ----------------------------------------------------------------------------


def _make_error_job(ds_name, wait_for_job_status):
    """Drive a rewrite job on ``ds_name`` into the ERROR state.

    Makes the dataset genuinely read-only (the remount is required: setting
    the property alone does not change an already-mounted filesystem), then
    creates the job directly against the daemon, whose walker fails with
    EROFS on the first file. Leaves the dataset writable again on return."""
    _stage_rewrite_work(ds_name, files=3)
    ssh(f"zfs set readonly=on {ds_name} && zfs unmount {ds_name} && zfs mount {ds_name}")
    try:
        job_uuid = ssh(f"python3 - <<'EOF'\n{_DAEMON_CREATE_JOB.format(ds=ds_name)}EOF").strip()
        tier_job_id = f"{ds_name}@{job_uuid}"
        assert wait_for_job_status(tier_job_id, {"COMPLETE", "ERROR"}, timeout=60) == "ERROR"
    finally:
        ssh(f"zfs set readonly=off {ds_name}")
    return tier_job_id


def test_error_job_raises_critical_alert(make_tier_ds, wait_for_job_status):
    ds_name = make_tier_ds("alert_err")
    tier_job_id = _make_error_job(ds_name, wait_for_job_status)

    alerts = _job_alerts_for(ds_name)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["klass"] == "TierJobError"
    assert alert["args"]["tier_job_id"] == tier_job_id
    assert "Read-only file system" in alert["args"]["error"]


# ----------------------------------------------------------------------------
# Degraded mode: a job listed in the global index whose per-dataset state DB
# is lost still gets an alert, with the unavailable details blanked.
# ----------------------------------------------------------------------------


def test_alerts_degrade_when_job_state_db_is_lost(make_tier_ds, wait_for_job_status):
    """The daemon keeps a global job index (``rewrite_jobs.mdb``) and one
    state DB per dataset. Deleting a per-dataset state DB leaves its jobs
    enumerable but unreadable in detail, so the source falls back to an
    empty error message / zeroed stats instead of dropping the alerts."""
    ds_complete = make_tier_ds("alert_nodb_c")
    ds_error = make_tier_ds("alert_nodb_e")
    complete_id = _complete_job(ds_complete, wait_for_job_status, files=2)
    error_id = _make_error_job(ds_error, wait_for_job_status)

    for ds_name in (ds_complete, ds_error):
        ssh(f"rm -rf /var/db/system/truenas_zfstierd/*{ds_name.split('/')[-1]}*")

    # The terminal-job set is unchanged, so the source would keep serving the
    # cached (fully detailed) alerts; a disable/enable cycle drops the cache
    # and forces recomputation against the crippled state.
    call("zfs.tier.update", {"enabled": False})
    try:
        assert _run_source() == []
    finally:
        call("zfs.tier.update", {"enabled": True})

    complete_alerts = _job_alerts_for(ds_complete)
    assert len(complete_alerts) == 1
    assert complete_alerts[0]["klass"] == "TierJobComplete"
    assert complete_alerts[0]["args"] == {
        "tier_job_id": complete_id,
        "files": 0,
        "tier": "REGULAR",
        "size": "0",
    }

    error_alerts = _job_alerts_for(ds_error)
    assert len(error_alerts) == 1
    assert error_alerts[0]["klass"] == "TierJobError"
    assert error_alerts[0]["args"] == {"tier_job_id": error_id, "error": ""}


# ----------------------------------------------------------------------------
# Job-alerts cache: served while the terminal-job set is unchanged, dropped
# on a disable/enable cycle.
# ----------------------------------------------------------------------------


def test_complete_alert_cached_across_dataset_deletion(tier_pool, wait_for_job_status):
    """Deleting a completed job's dataset does not change the terminal-job
    set (LMDB records outlive the dataset), so the cached COMPLETE alert is
    still served — a recomputation would drop it because the dataset no
    longer resolves to any tier info. Disabling tiering clears the cache, so
    after re-enabling, the recomputation does drop the alert."""
    ds_name = f"{tier_pool['name']}/alert_cache_{time.monotonic_ns()}"
    call("pool.dataset.create", {"name": ds_name})
    try:
        _complete_job(ds_name, wait_for_job_status)
        assert len(_job_alerts_for(ds_name)) == 1

        call("pool.dataset.delete", ds_name, {"recursive": True})
        assert len(_job_alerts_for(ds_name)) == 1  # cache hit

        call("zfs.tier.update", {"enabled": False})
        try:
            assert _run_source() == []  # gate short-circuits, cache dropped
        finally:
            call("zfs.tier.update", {"enabled": True})

        assert _job_alerts_for(ds_name) == []  # recomputed: dataset is gone
    finally:
        if call("pool.dataset.query", [["name", "=", ds_name]]):
            call("pool.dataset.delete", ds_name, {"recursive": True})


# ----------------------------------------------------------------------------
# SPECIAL-vdev usage thresholds. Runs last: it fills the SPECIAL vdev.
# ----------------------------------------------------------------------------


@pytest.mark.timeout(600)
def test_special_vdev_warning_and_critical_alerts(tier_pool):
    """With max_used_percentage=70 (reserve untouched at its default), the
    thresholds land at warning=60 / critical=70 while the kernel's spill
    point stays at 75 — so both alert levels are reachable by filling.

    The fill copies an incompressible tmpfs seed file cross-filesystem:
    an on-pool source would be reflink-cloned by cp (ZFS block cloning)
    and allocate nothing."""
    pool_name = tier_pool["name"]
    original_cap = call("zfs.tier.config")["max_used_percentage"]
    call("zfs.tier.update", {"max_used_percentage": 70})
    filler = f"{pool_name}/alert_fill_{time.monotonic_ns()}"
    call("pool.dataset.create", {"name": filler})
    call("zfs.tier.dataset_set_tier", {"dataset_name": filler, "tier_type": "PERFORMANCE"})
    ssh(f"dd if=/dev/urandom of={SEED} bs=1M count=512 2>/dev/null")

    counter = 0

    def fill_to(target_pct, batch):
        """Copy seed files (2 in parallel per round) until the SPECIAL usage
        ratio crosses target_pct. Small batches so the overshoot cannot jump
        the 60–70 warning window."""
        nonlocal counter
        deadline = time.monotonic() + 480
        while _special_vdev_pct(pool_name) < target_pct:
            assert time.monotonic() < deadline, (
                f"fill to {target_pct}% too slow, at {_special_vdev_pct(pool_name):.1f}%"
            )
            copies = " ".join(f"cp {SEED} /mnt/{filler}/f{counter + i} &" for i in range(batch))
            counter += batch
            ssh(f"{copies} wait; zpool sync {pool_name}")

    try:
        # Below both thresholds: no SPECIAL-vdev alerts for any pool (this
        # also exercises the skip of pools without a SPECIAL vdev, e.g. the
        # system's main pool).
        assert all(not a["klass"].startswith("TierSpecialVdev") for a in _run_source())

        fill_to(61, batch=2)
        alerts = _special_vdev_alerts_for(pool_name)
        assert [a["klass"] for a in alerts] == ["TierSpecialVdevWarning"]
        assert alerts[0]["args"] == {"pool_name": pool_name, "threshold": 60}

        fill_to(71, batch=2)
        alerts = _special_vdev_alerts_for(pool_name)
        assert [a["klass"] for a in alerts] == ["TierSpecialVdevCritical"]
        assert alerts[0]["args"] == {"pool_name": pool_name, "threshold": 70}
    finally:
        ssh(f"rm -f {SEED}")
        call("pool.dataset.delete", filler, {"recursive": True})
        call("zfs.tier.update", {"max_used_percentage": original_cap})
