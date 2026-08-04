"""Shared fixtures for the zfs.tier integration test suite.

The pool fixture uses a 3-wide RAIDZ1 data vdev plus a 3-wide RAIDZ1 SPECIAL
vdev (6 disks total). All tier tests require:

  - An Enterprise license (zfs.tier.update is license-gated).
  - At least 6 unused disks on the target VM.
"""

import contextlib
import time

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.system import reset_systemd_svcs

# Daemon test hook: while this file exists, rewrite jobs wait the number of
# milliseconds it contains after each regular file. The daemon reads it once
# per job start, and the wait is interruptible by cancellation. It lives in
# the daemon's runtime directory, so a reboot clears it.
SLOW_REWRITE_SENTINEL = "/var/run/truenas_zfstierd/slow_rewrite"
SLOW_REWRITE_DELAY_MS = 100


@pytest.fixture(scope="module")
def tier_pool():
    """A pool with a SPECIAL vdev, with tiering globally enabled."""
    if not call("system.is_enterprise"):
        pytest.skip("ZFS tiering requires an Enterprise license")

    unused = call("disk.get_unused")
    if len(unused) < 6:
        pytest.fail("Need at least 6 unused disks for a 3+3 RAIDZ1 tier pool")

    data_disks = [d["name"] for d in unused[:3]]
    special_disks = [d["name"] for d in unused[3:6]]

    with another_pool(
        {
            "topology": {
                "data": [{"type": "RAIDZ1", "disks": data_disks}],
                "special": [{"type": "RAIDZ1", "disks": special_disks}],
            },
            "allow_duplicate_serials": True,
        }
    ) as pool:
        original_config = call("zfs.tier.config")
        call("zfs.tier.update", {"enabled": True})
        reset_systemd_svcs("truenas_zfstierd")
        ssh("systemctl start truenas_zfstierd")
        for _ in range(20):
            if (
                ssh("systemctl is-active truenas_zfstierd 2>/dev/null || true").strip()
                == "active"
            ):
                break
            time.sleep(0.5)
        else:
            raise AssertionError(
                "truenas_zfstierd failed to reach 'active' state within 10s"
            )
        try:
            yield pool
        finally:
            call(
                "zfs.tier.update",
                {
                    k: original_config[k]
                    for k in (
                        "enabled",
                        "max_concurrent_jobs",
                        "max_used_percentage",
                        "special_class_metadata_reserve_pct",
                    )
                },
            )


@pytest.fixture()
def slow_rewrite(tier_pool):
    """Slow rewrite jobs down to SLOW_REWRITE_DELAY_MS per file for this test.

    Gives a job on an N-file dataset a lifetime of at least N * delay, so
    tests can observe QUEUED/RUNNING, event-source polls, and cancellation
    mid-run without staging gigabytes of data. The daemon reads the sentinel
    when a job starts, so it must be active before the job is created;
    cancellation interrupts the per-file wait promptly."""
    ssh(
        f"mkdir -p {SLOW_REWRITE_SENTINEL.rsplit('/', 1)[0]} && "
        f"echo {SLOW_REWRITE_DELAY_MS} > {SLOW_REWRITE_SENTINEL}"
    )
    try:
        yield
    finally:
        ssh(f"rm -f {SLOW_REWRITE_SENTINEL}")


def _cancel_active_jobs(ds_name):
    """Cancel any QUEUED/RUNNING rewrite job on ``ds_name``. The daemon's
    cancel waits (bounded) for the walker to stop, so on return the dataset
    is normally no longer held open by a rewrite job."""
    for job in call("zfs.tier.rewrite_job_query", {}):
        if job["dataset_name"] == ds_name and job["status"] in (
            "QUEUED",
            "RUNNING",
        ):
            try:
                call(
                    "zfs.tier.rewrite_job_cancel",
                    {"tier_job_id": job["tier_job_id"]},
                )
            except Exception:
                pass


def _delete_dataset(ds_name, attempts=5, delay=2):
    """pool.dataset.delete with retries on a busy unmount. The daemon's
    abort wait is bounded, so a just-cancelled job's walker can still be
    draining (holding fds inside the dataset) when the first delete lands."""
    for attempt in range(attempts):
        try:
            call("pool.dataset.delete", ds_name, {"recursive": True})
            return
        except Exception as e:
            if attempt == attempts - 1 or "busy" not in str(e).lower():
                raise
        time.sleep(delay)


@pytest.fixture()
def tier_ds(tier_pool):
    """A fresh dataset on the tier pool, cleaned up after each test.

    Cancels any pending rewrite job on this dataset before deletion so the
    pool.dataset.delete unmount doesn't fail with EZFS_BUSY."""
    ds_name = f"{tier_pool['name']}/tier_test_{time.monotonic_ns()}"
    call("pool.dataset.create", {"name": ds_name})
    try:
        yield ds_name
    finally:
        _cancel_active_jobs(ds_name)
        _delete_dataset(ds_name)


@pytest.fixture()
def make_tier_ds(tier_pool):
    """Factory for additional datasets on the tier pool, with the same
    cancel-active-jobs-then-delete cleanup as ``tier_ds``. For tests that
    need more than one dataset at a time."""
    created = []

    def _make(prefix):
        ds_name = f"{tier_pool['name']}/{prefix}_{time.monotonic_ns()}"
        call("pool.dataset.create", {"name": ds_name})
        created.append(ds_name)
        return ds_name

    try:
        yield _make
    finally:
        for ds_name in reversed(created):
            _cancel_active_jobs(ds_name)
            _delete_dataset(ds_name)


@pytest.fixture()
def tier_ds_performance(tier_ds):
    """A dataset pre-set to the PERFORMANCE tier."""
    call(
        "zfs.tier.dataset_set_tier",
        {"dataset_name": tier_ds, "tier_type": "PERFORMANCE"},
    )
    return tier_ds


@pytest.fixture()
def tier_ds_regular(tier_ds):
    """A dataset explicitly set to the REGULAR tier (no inherited PERFORMANCE)."""
    call(
        "zfs.tier.dataset_set_tier",
        {"dataset_name": tier_ds, "tier_type": "REGULAR"},
    )
    return tier_ds


def _write_many_small_files(ds, n=200, size_mb=1):
    """Create `n` separate `size_mb`-MiB files so the rewrite walker visits
    `n` inodes AND has actual blocks to move between vdev classes.

    With the slow-rewrite sentinel active, `n` files also put a floor of
    `n * SLOW_REWRITE_DELAY_MS` on the job's lifetime, so the total staged
    data can stay small enough not to pressure the pool's space thresholds."""
    ssh(
        f"cd /mnt/{ds} && seq 1 {n} | "
        f"xargs -P 16 -I X dd if=/dev/urandom of=fX bs=1M count={size_mb} 2>/dev/null"
    )


@pytest.fixture()
def tier_ds_with_work(tier_ds, slow_rewrite):
    """A dataset pre-staged so the next rewrite job has real work to do and
    stays observable while doing it.

    Workflow: set tier=PERFORMANCE (special_small_blocks=16M, so writes
    land on SPECIAL), create MiB-sized files, then flip tier=REGULAR
    (special_small_blocks=0). Every block is now physically on SPECIAL
    but should be on NORMAL — the rewrite walker has to visit each file
    and move its blocks, and the slow-rewrite sentinel holds the job at
    SLOW_REWRITE_DELAY_MS per file (>= 20 s lifetime at the defaults) so
    per-file callbacks flush LMDB state and tests can observe the job
    before it completes. Active-job cancellation on teardown is handled
    by the nested ``tier_ds`` fixture."""
    call(
        "zfs.tier.dataset_set_tier",
        {"dataset_name": tier_ds, "tier_type": "PERFORMANCE"},
    )
    _write_many_small_files(tier_ds)
    call(
        "zfs.tier.dataset_set_tier",
        {"dataset_name": tier_ds, "tier_type": "REGULAR"},
    )
    return tier_ds


@contextlib.contextmanager
def _toggle_enabled(value):
    original = call("zfs.tier.config")["enabled"]
    if original == value:
        yield
        return
    call("zfs.tier.update", {"enabled": value})
    try:
        yield
    finally:
        call("zfs.tier.update", {"enabled": original})


@pytest.fixture()
def disabled_tier(tier_pool):
    """Globally disable tiering for the duration of the test, then restore."""
    with _toggle_enabled(False):
        yield


def _wait_for_job_status(tier_job_id, desired_statuses, timeout=60, interval=1):
    """Poll zfs.tier.rewrite_job_status until status is in desired_statuses.

    Tolerates a transient "entry not found" while the daemon hasn't yet
    written initial job state to LMDB (a short window right after
    rewrite_job_create returns, especially for small datasets)."""
    deadline = time.monotonic() + timeout
    last_status = None
    last_err = None
    while time.monotonic() < deadline:
        try:
            last_status = call(
                "zfs.tier.rewrite_job_status", {"tier_job_id": tier_job_id}
            )["status"]
        except CallError as e:
            if "entry not found" in str(e):
                last_err = e
                time.sleep(interval)
                continue
            raise
        if last_status in desired_statuses:
            return last_status
        time.sleep(interval)
    raise TimeoutError(
        f"{tier_job_id!r} did not reach {desired_statuses} within {timeout}s "
        f"(last status: {last_status!r}, last error: {last_err!r})"
    )


@pytest.fixture()
def wait_for_job_status():
    """Return the polling helper as a callable. Used as a fixture so tests
    don't need to import from conftest.py (relative imports break when
    pytest loads each test file as a top-level module)."""
    return _wait_for_job_status


@pytest.fixture(autouse=True)
def _reset_zfstierd_rate_limit(request):
    """Clear systemd's StartLimitBurst counter on truenas_zfstierd before each
    test that touches it, so cascading restarts across tests can't hit the
    unit's ``StartLimitBurst=5 / StartLimitIntervalSec=300``."""
    if "tier_pool" not in request.fixturenames:
        return
    reset_systemd_svcs("truenas_zfstierd")
