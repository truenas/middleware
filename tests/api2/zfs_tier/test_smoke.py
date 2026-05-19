"""Smoke tests for the zfs.tier plugin: core config / job / set-tier paths.

The 3+3 RAIDZ1 tier pool fixture (and the Enterprise-license skip) live in
``conftest.py`` alongside this file. Tests run on a TrueNAS box with at
least 6 unused disks.
"""

import errno
import json
import pprint
import time
import pytest

from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, client, ssh


def test_config_fields():
    """zfs.tier.config returns the expected schema."""
    config = call("zfs.tier.config")
    assert isinstance(config["id"], int)
    assert isinstance(config["enabled"], bool)
    assert isinstance(config["max_concurrent_jobs"], int)
    assert isinstance(config["max_used_percentage"], int)
    assert 1 <= config["max_concurrent_jobs"] <= 10
    assert 70 <= config["max_used_percentage"] <= 95


def test_config_update_max_concurrent_jobs(tier_pool):
    original = call("zfs.tier.config")["max_concurrent_jobs"]
    new_val = 5 if original != 5 else 3
    try:
        result = call("zfs.tier.update", {"max_concurrent_jobs": new_val})
        assert result["max_concurrent_jobs"] == new_val
        assert call("zfs.tier.config")["max_concurrent_jobs"] == new_val
    finally:
        call("zfs.tier.update", {"max_concurrent_jobs": original})


def test_config_update_max_used_percentage(tier_pool):
    original = call("zfs.tier.config")["max_used_percentage"]
    new_val = 90 if original != 90 else 85
    try:
        result = call("zfs.tier.update", {"max_used_percentage": new_val})
        assert result["max_used_percentage"] == new_val
        assert call("zfs.tier.config")["max_used_percentage"] == new_val
    finally:
        call("zfs.tier.update", {"max_used_percentage": original})


def test_dataset_set_tier_performance(tier_ds):
    result = call(
        "zfs.tier.dataset_set_tier",
        {
            "dataset_name": tier_ds,
            "tier_type": "PERFORMANCE",
        },
    )
    assert result["tier_type"] == "PERFORMANCE"
    assert result["tier_job"] is None

    # Verify the ZFS property was actually set (16 MiB)
    props = call(
        "zfs.resource.query",
        {"paths": [tier_ds], "properties": ["special_small_blocks"]},
    )
    assert props[0]["properties"]["special_small_blocks"]["value"] == 16 * 1024 * 1024


def test_dataset_set_tier_regular(tier_ds):
    # Set PERFORMANCE first, then revert to REGULAR
    call(
        "zfs.tier.dataset_set_tier",
        {"dataset_name": tier_ds, "tier_type": "PERFORMANCE"},
    )

    result = call(
        "zfs.tier.dataset_set_tier",
        {
            "dataset_name": tier_ds,
            "tier_type": "REGULAR",
        },
    )
    assert result["tier_type"] == "REGULAR"
    assert result["tier_job"] is None

    props = call(
        "zfs.resource.query",
        {"paths": [tier_ds], "properties": ["special_small_blocks"]},
    )
    assert props[0]["properties"]["special_small_blocks"]["value"] == 0


def test_dataset_set_tier_with_migration(tier_ds):
    # Populate with enough data that the rewrite job stays active across the
    # event source's 5s poll window.
    ssh(
        f"dd if=/dev/urandom of=/mnt/{tier_ds}/fillfile bs=1M count=100 "
        "conv=fdatasync 2>/dev/null"
    )

    with client() as c:
        events = []
        c.subscribe(
            "zfs.tier.rewrite_job_query",
            lambda t, **m: events.append((t, m)),
            sync=True,
        )

        result = c.call(
            "zfs.tier.dataset_set_tier",
            {
                "dataset_name": tier_ds,
                "tier_type": "PERFORMANCE",
                "move_existing_data": True,
            },
        )
        time.sleep(7)

    assert result["tier_type"] == "PERFORMANCE"
    assert result["tier_job"] is not None
    assert result["tier_job"]["dataset_name"] == tier_ds
    assert result["tier_job"]["status"] in ("QUEUED", "RUNNING", "COMPLETE")

    matching = [
        e for e in events
        if e[0] == "ADDED" and e[1]["fields"].get("dataset_name") == tier_ds
    ]
    assert matching, pprint.pformat(events)


def test_dataset_set_tier_globally_disabled():
    """Returns EINVAL when tiering is globally disabled."""
    if not call("system.is_enterprise"):
        pytest.skip("Requires enterprise to toggle enabled flag")

    original = call("zfs.tier.config")["enabled"]
    try:
        call("zfs.tier.update", {"enabled": False})
        with pytest.raises(ValidationError) as ve:
            call(
                "zfs.tier.dataset_set_tier",
                {
                    "dataset_name": "tank/nonexistent",
                    "tier_type": "PERFORMANCE",
                },
            )
        assert ve.value.attribute == "zfs_tier_dataset_set_tier"
        assert ve.value.errno == errno.EINVAL
    finally:
        call("zfs.tier.update", {"enabled": original})


def test_dataset_set_tier_no_special_vdev(tier_pool):
    """Returns EINVAL for a dataset on a pool without a SPECIAL vdev."""
    # Use the default test pool which has no SPECIAL vdev
    with dataset("tier_no_special_test") as ds:
        with pytest.raises(ValidationError) as ve:
            call(
                "zfs.tier.dataset_set_tier",
                {
                    "dataset_name": ds,
                    "tier_type": "PERFORMANCE",
                },
            )
        assert ve.value.attribute == "zfs_tier_dataset_set_tier"
        assert ve.value.errno == errno.EINVAL
        assert "SPECIAL vdev" in ve.value.errmsg


def test_rewrite_job_create_returns_queued_or_running(tier_ds):
    entry = call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds})
    assert entry["dataset_name"] == tier_ds
    assert "@" in entry["tier_job_id"]
    assert entry["status"] in ("QUEUED", "RUNNING")


def _fill(ds):
    """Write enough data that the daemon's job stays active long enough to
    persist LMDB state and emit events. The daemon doesn't write LMDB state
    on submit for RUNNING jobs, and reporting_write_interval=60s means
    instant-completing jobs (empty/small datasets) leave no trace."""
    ssh(
        f"dd if=/dev/urandom of=/mnt/{ds}/fillfile bs=1M count=100 "
        "conv=fdatasync 2>/dev/null"
    )


def test_rewrite_job_create_fires_added_event(tier_ds):
    _fill(tier_ds)
    with client() as c:
        events = []
        c.subscribe(
            "zfs.tier.rewrite_job_query",
            lambda t, **m: events.append((t, m)),
            sync=True,
        )
        entry = c.call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds})
        # Event source polls every 5s; wait long enough for the next tick.
        time.sleep(7)

    matching = [e for e in events if e[1].get("id") == entry["tier_job_id"]]
    assert matching, pprint.pformat(events)
    assert matching[0][0] == "ADDED"
    assert matching[0][1]["collection"] == "zfs.tier.rewrite_job_query"
    assert matching[0][1]["msg"] == "added"
    assert matching[0][1]["id"] == entry["tier_job_id"]
    assert matching[0][1]["fields"]["dataset_name"] == tier_ds


def test_rewrite_job_create_duplicate_raises_eexist(tier_ds_with_work):
    """Creating a second job for the same dataset raises EEXIST.

    _raise_client_error maps JOB_ALREADY_EXISTS → singular ValidationError."""
    call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds_with_work})
    with pytest.raises(ValidationError) as ve:
        call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds_with_work})
    assert ve.value.errno == errno.EEXIST


def test_rewrite_job_query_returns_created_job(tier_ds):
    _fill(tier_ds)
    entry = call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds})
    jobs = call("zfs.tier.rewrite_job_query", {})
    ids = [j["tier_job_id"] for j in jobs]
    assert entry["tier_job_id"] in ids


def test_rewrite_job_query_status_filter(tier_ds_with_work, wait_for_job_status):
    entry = call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds_with_work})
    # The daemon may not write LMDB state for several seconds; wait until
    # the status RPC can find an entry before reading current_status.
    current_status = wait_for_job_status(
        entry["tier_job_id"],
        {"QUEUED", "RUNNING", "COMPLETE", "CANCELLED", "STOPPED", "ERROR"},
        timeout=30,
    )

    matching = call("zfs.tier.rewrite_job_query", {"status": [current_status]})
    assert any(j["tier_job_id"] == entry["tier_job_id"] for j in matching)

    # Filter by a different terminal status — should not appear (unless job already transitioned)
    non_matching_status = "CANCELLED"
    if current_status != non_matching_status:
        non_matching = call(
            "zfs.tier.rewrite_job_query", {"status": [non_matching_status]}
        )
        assert all(j["tier_job_id"] != entry["tier_job_id"] for j in non_matching)


def test_rewrite_job_status_shape(tier_ds_with_work, wait_for_job_status):
    entry = call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds_with_work})
    wait_for_job_status(
        entry["tier_job_id"],
        {"QUEUED", "RUNNING", "COMPLETE", "CANCELLED", "STOPPED", "ERROR"},
        timeout=30,
    )
    status = call("zfs.tier.rewrite_job_status", {"tier_job_id": entry["tier_job_id"]})

    assert status["tier_job_id"] == entry["tier_job_id"]
    assert status["dataset_name"] == tier_ds
    assert status["job_uuid"] == entry["job_uuid"]
    assert status["status"] in (
        "QUEUED",
        "RUNNING",
        "COMPLETE",
        "CANCELLED",
        "STOPPED",
        "ERROR",
    )
    # stats may be None if the job hasn't started yet
    assert status["stats"] is None or isinstance(status["stats"], dict)
    assert status["error"] is None or isinstance(status["error"], str)


def test_rewrite_job_status_completes(tier_ds, wait_for_job_status):
    """A job on an empty dataset should reach COMPLETE quickly."""
    entry = call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds})
    final = wait_for_job_status(
        entry["tier_job_id"], {"COMPLETE", "ERROR"}, timeout=60
    )
    assert final == "COMPLETE"


def test_rewrite_job_abort_fires_changed_event(tier_ds_with_work, wait_for_job_status):
    entry = call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds_with_work})
    # Give the daemon time to register the job in LMDB so the event source's
    # first poll captures it before we cancel.
    wait_for_job_status(
        entry["tier_job_id"], {"QUEUED", "RUNNING"}, timeout=30
    )

    with client() as c:
        events = []
        c.subscribe(
            "zfs.tier.rewrite_job_query",
            lambda t, **m: events.append((t, m)),
            sync=True,
        )
        # First poll captures the RUNNING entry as ADDED on the initial pass.
        time.sleep(1)
        c.call("zfs.tier.rewrite_job_cancel", {"tier_job_id": entry["tier_job_id"]})
        # Next poll (5s) sees the CANCELLED status and emits CHANGED.
        time.sleep(7)

    changed = [
        e for e in events
        if e[0] == "CHANGED" and e[1]["fields"].get("tier_job_id") == entry["tier_job_id"]
    ]
    assert changed, pprint.pformat(events)
    assert changed[-1][1]["fields"]["status"] == "CANCELLED"


def test_rewrite_job_abort_nonexistent_raises(tier_pool):
    """tier_pool ensures the daemon is running so the JSON-RPC call lands."""
    with pytest.raises(ValidationError) as ve:
        call(
            "zfs.tier.rewrite_job_cancel",
            {"tier_job_id": f"{tier_pool['name']}/nonexistent@00000000-0000-0000-0000-000000000000"},
        )
    assert ve.value.errno == errno.ENOENT


def test_rewrite_job_status_event_source(tier_ds):
    """The polling event source emits CHANGED events while a job is active."""
    ssh(
        f"for i in $(seq 1 100); do dd if=/dev/urandom of=/mnt/{tier_ds}/f$i bs=4k count=1 2>/dev/null; done"
    )
    call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds})

    arg = json.dumps({"dataset_name": tier_ds})
    with client() as c:
        events = []
        c.subscribe(
            f"zfs.tier.rewrite_job_status:{arg}",
            lambda t, **m: events.append((t, m)),
            sync=True,
        )
        time.sleep(6)  # event source polls every 2s

    assert events, "No events received from rewrite_job_status event source"
    assert events[0][0] == "CHANGED"
    assert events[0][1]["fields"]["dataset_name"] == tier_ds
    assert "status" in events[0][1]["fields"]
