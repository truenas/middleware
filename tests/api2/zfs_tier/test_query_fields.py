"""The `tier` field on dataset and resource query namespaces.

This is the headline claim of commit cfef5e8053: pool.dataset.query and
zfs.resource.query (the latter requires get_tier=True) both expose the
underlying dataset's tier as a read-only TierInfo struct, or null when
unsupported.

Implementation under test:
  - src/middlewared/middlewared/plugins/zfs/query_impl.py:50-51, 113-126
  - src/middlewared/middlewared/plugins/zfs/resource_crud.py:352-364
  - src/middlewared/middlewared/plugins/pool_/dataset.py:142-153
  - src/middlewared/middlewared/plugins/pool_/dataset_query_utils.py:953-954
  - src/middlewared/middlewared/plugins/zfs/tier.py:160-215 (get_dataset_tier_info_cached)
"""

import contextlib
import time

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


@contextlib.contextmanager
def _temporarily_disabled():
    original = call("zfs.tier.config")["enabled"]
    if not original:
        yield
        return
    call("zfs.tier.update", {"enabled": False})
    try:
        yield
    finally:
        call("zfs.tier.update", {"enabled": original})


# ----------------------------------------------------------------------------
# pool.dataset.query
# ----------------------------------------------------------------------------


def test_pool_dataset_query_returns_tier_field(tier_ds):
    """FILESYSTEM entries on a tier-capable pool carry a `tier` field."""
    ds = call("pool.dataset.query", [["name", "=", tier_ds]], {"get": True})
    assert "tier" in ds
    # tier is either a TierInfo dict or None
    if ds["tier"] is not None:
        assert "tier_type" in ds["tier"]
        assert ds["tier"]["tier_type"] in ("REGULAR", "PERFORMANCE")
        assert "tier_job" in ds["tier"]


def test_pool_dataset_query_tier_reflects_performance(tier_ds_performance):
    ds = call(
        "pool.dataset.query",
        [["name", "=", tier_ds_performance]],
        {"get": True},
    )
    assert ds["tier"] is not None
    assert ds["tier"]["tier_type"] == "PERFORMANCE"


def test_pool_dataset_query_tier_reflects_regular(tier_ds_regular):
    ds = call(
        "pool.dataset.query",
        [["name", "=", tier_ds_regular]],
        {"get": True},
    )
    assert ds["tier"] is not None
    assert ds["tier"]["tier_type"] == "REGULAR"


def test_pool_dataset_query_tier_is_null_when_globally_disabled(tier_ds):
    """When zfs.tier.config.enabled is False, dataset_query_utils.py:953 skips
    the tier injection entirely, so the key is absent from the row dict.

    A future change might switch to always setting tier=None — accept both."""
    with _temporarily_disabled():
        ds = call("pool.dataset.query", [["name", "=", tier_ds]], {"get": True})
        assert ds.get("tier") is None


def test_pool_dataset_query_tier_is_null_on_pool_without_special(tier_pool):
    """Datasets on pools without a SPECIAL vdev report tier=None even with
    tiering globally enabled (get_dataset_tier_info_cached:170-184)."""
    with dataset("tier_no_special_q") as ds:
        row = call("pool.dataset.query", [["name", "=", ds]], {"get": True})
        assert row["tier"] is None


def test_pool_dataset_query_tier_job_populated_after_job_created(
    tier_ds_with_work, wait_for_job_status
):
    """After creating a rewrite job, the dataset's tier.tier_job reports
    the job ID (matches get_last_job result). Waits until the daemon has
    flushed initial job state to LMDB before reading the query field."""
    entry = call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds_with_work})
    wait_for_job_status(
        entry["tier_job_id"],
        {"QUEUED", "RUNNING", "COMPLETE", "CANCELLED", "STOPPED", "ERROR"},
        timeout=30,
    )
    ds = call("pool.dataset.query", [["name", "=", tier_ds_with_work]], {"get": True})
    assert ds["tier"] is not None
    tier_job = ds["tier"]["tier_job"]
    assert tier_job is not None
    assert tier_job["tier_job_id"] == entry["tier_job_id"]
    assert tier_job["dataset_name"] == tier_ds_with_work
    assert tier_job["job_uuid"] == entry["job_uuid"]
    assert tier_job["status"] in (
        "QUEUED",
        "RUNNING",
        "COMPLETE",
        "CANCELLED",
        "STOPPED",
        "ERROR",
    )


def test_pool_dataset_query_volume_has_null_tier(tier_pool):
    """ZVOLs are not FILESYSTEM resources — query_impl.py:50 only computes
    tier on FILESYSTEM. The field defaults to None on the Pydantic model."""
    zvol_name = f"{tier_pool['name']}/tier_zvol_{time.monotonic_ns()}"
    call(
        "pool.dataset.create",
        {"name": zvol_name, "type": "VOLUME", "volsize": 1024 * 1024 * 32},
    )
    try:
        row = call("pool.dataset.query", [["name", "=", zvol_name]], {"get": True})
        # tier may be absent from the model for volumes, or explicitly None
        assert row.get("tier") is None
    finally:
        call("pool.dataset.delete", zvol_name, {"recursive": True})


# ----------------------------------------------------------------------------
# zfs.resource.query
# ----------------------------------------------------------------------------


def test_zfs_resource_query_tier_requires_get_tier_flag(tier_ds_performance):
    """Without get_tier=True, the resource query doesn't compute tier (tier
    is None / absent). With get_tier=True, the field carries TierInfo."""
    rows_default = call(
        "zfs.resource.query",
        {"paths": [tier_ds_performance]},
    )
    assert rows_default
    assert rows_default[0].get("tier") is None

    rows_with_tier = call(
        "zfs.resource.query",
        {"paths": [tier_ds_performance], "get_tier": True},
    )
    assert rows_with_tier
    assert rows_with_tier[0]["tier"] is not None
    assert rows_with_tier[0]["tier"]["tier_type"] == "PERFORMANCE"


def test_zfs_resource_query_get_tier_returns_null_when_disabled(tier_ds_performance):
    """get_tier=True still returns None when zfs.tier.config.enabled is False."""
    with _temporarily_disabled():
        rows = call(
            "zfs.resource.query",
            {"paths": [tier_ds_performance], "get_tier": True},
        )
        assert rows
        assert rows[0]["tier"] is None


def test_zfs_resource_query_get_tier_returns_null_on_pool_without_special(tier_pool):
    """get_tier=True returns None for datasets on a pool without a SPECIAL vdev."""
    with dataset("tier_resource_no_special") as ds:
        rows = call(
            "zfs.resource.query",
            {"paths": [ds], "get_tier": True},
        )
        assert rows
        assert rows[0]["tier"] is None


# ----------------------------------------------------------------------------
# Cross-check: set_tier result matches the next query
# ----------------------------------------------------------------------------


def test_set_tier_round_trip_through_pool_dataset_query(tier_ds):
    """Setting tier via zfs.tier.dataset_set_tier should be visible on a
    subsequent pool.dataset.query."""
    call(
        "zfs.tier.dataset_set_tier",
        {"dataset_name": tier_ds, "tier_type": "PERFORMANCE"},
    )
    row1 = call("pool.dataset.query", [["name", "=", tier_ds]], {"get": True})
    assert row1["tier"]["tier_type"] == "PERFORMANCE"

    call(
        "zfs.tier.dataset_set_tier",
        {"dataset_name": tier_ds, "tier_type": "REGULAR"},
    )
    row2 = call("pool.dataset.query", [["name", "=", tier_ds]], {"get": True})
    assert row2["tier"]["tier_type"] == "REGULAR"
