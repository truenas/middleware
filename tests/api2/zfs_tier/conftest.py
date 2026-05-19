"""Shared fixtures for the zfs.tier integration test suite.

The pool fixture uses a 3-wide RAIDZ1 data vdev plus a 3-wide RAIDZ1 SPECIAL
vdev (6 disks total). All tier tests require:

  - An Enterprise license (zfs.tier.update is license-gated).
  - At least 6 unused disks on the target VM.
"""

import contextlib
import time

import pytest

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call


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
        # zfs.tier.update sends RELOAD/RESTART but won't START a stopped
        # daemon. Start it explicitly (idempotent if already running).
        call(
            "service.control",
            "START",
            "truenas_zfstierd",
            {"silent": False},
            job=True,
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
    """Poll zfs.tier.rewrite_job_status until status is in desired_statuses."""
    deadline = time.monotonic() + timeout
    last_status = None
    while time.monotonic() < deadline:
        last_status = call(
            "zfs.tier.rewrite_job_status", {"tier_job_id": tier_job_id}
        )["status"]
        if last_status in desired_statuses:
            return last_status
        time.sleep(interval)
    raise TimeoutError(
        f"{tier_job_id!r} did not reach {desired_statuses} within {timeout}s "
        f"(last status: {last_status!r})"
    )


@pytest.fixture()
def wait_for_job_status():
    """Return the polling helper as a callable. Used as a fixture so tests
    don't need to import from conftest.py (relative imports break when
    pytest loads each test file as a top-level module)."""
    return _wait_for_job_status
