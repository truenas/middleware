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


@pytest.fixture(scope="module")
def tier_pool():
    """A pool with a SPECIAL vdev, with tiering globally enabled."""
    unused = call("disk.get_unused")
    if len(unused) < 6:
        pytest.skip("Need at least 6 unused disks for a 3+3 RAIDZ1 tier pool")
    if not call("system.is_enterprise"):
        pytest.skip("ZFS tiering requires an Enterprise license")

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
            if ssh("systemctl is-active truenas_zfstierd 2>/dev/null || true").strip() == "active":
                break
            time.sleep(0.5)
        else:
            raise AssertionError("truenas_zfstierd failed to reach 'active' state within 10s")
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
def tier_ds(tier_pool):
    """A fresh dataset on the tier pool, cleaned up after each test."""
    ds_name = f"{tier_pool['name']}/tier_test_{time.monotonic_ns()}"
    call("pool.dataset.create", {"name": ds_name})
    try:
        yield ds_name
    finally:
        call("pool.dataset.delete", ds_name, {"recursive": True})


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


def _write_many_small_files(ds, n=10000, size=4096):
    """Create `n` separate small files so the rewrite daemon's walker visits
    `n` inodes. The daemon's reporting_callback_interval=1 means the
    per-file callback fires after every iterated object, and (with the
    default stats_flush_interval=1s) at least one LMDB flush happens for
    every second the walker is busy — many small files keep it busy long
    enough to persist state, where a single large file gets no per-file
    callbacks at all."""
    ssh(
        f"cd /mnt/{ds} && seq 1 {n} | "
        f"xargs -P 16 -I X dd if=/dev/urandom of=fX bs={size} count=1 2>/dev/null"
    )


@pytest.fixture()
def tier_ds_with_work(tier_ds):
    """A dataset pre-staged so the next rewrite_job has real work to do.

    Workflow: set tier=PERFORMANCE (special_small_blocks=16M, so small
    writes land on SPECIAL), create 10000 small files, then flip
    tier=REGULAR (special_small_blocks=0). Every block is now physically
    on SPECIAL but should be on NORMAL — the rewrite walker has to visit
    each file and move its block, keeping the job alive long enough for
    the per-file callbacks to flush LMDB state."""
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
