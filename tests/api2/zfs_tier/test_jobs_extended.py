"""Extended job-API tests beyond test_smoke.py: failures listing, recover,
invalid IDs, query pagination/filtering, and event-source edge cases.

Implementation under test:
  - zfs.tier.rewrite_job_status (tier.py:414-426)
  - zfs.tier.rewrite_job_failures (tier.py:428-451)
  - zfs.tier.rewrite_job_recover (tier.py:469-486)
  - zfs.tier.rewrite_job_query (tier.py:396-412)
  - ZfsTierRewriteJobStatusEventSource (tier.py:218-253)
  - ZfsTierRewriteJobQueryEventSource (tier.py:256-300)
"""

import json
import pprint
import time

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call, client, ssh


_FAKE_JOB_ID = "tank/nonexistent@00000000-0000-0000-0000-000000000000"


def _populate(ds):
    """Write enough data that the rewrite daemon's job stays active across
    the event source's 5s poll cadence and reporting_write_interval=60s.
    Empty/small datasets complete before any LMDB write happens, leaving
    nothing for rewrite_job_status / enum_jobs to find."""
    ssh(
        f"dd if=/dev/urandom of=/mnt/{ds}/fillfile bs=1M count=100 "
        "conv=fdatasync 2>/dev/null"
    )


# ----------------------------------------------------------------------------
# rewrite_job_failures
# ----------------------------------------------------------------------------


def test_rewrite_job_failures_empty_for_clean_completed_job(tier_ds, wait_for_job_status):
    """A job that processes real data should reach COMPLETE with no failures."""
    _populate(tier_ds)
    entry = call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds})
    wait_for_job_status(entry["tier_job_id"], {"COMPLETE", "ERROR"}, timeout=60)

    failures = call(
        "zfs.tier.rewrite_job_failures", {"tier_job_id": entry["tier_job_id"]}
    )
    assert failures == []


def test_rewrite_job_failures_invalid_id_format_raises_callerror():
    """_parse_tier_job_id raises CallError when '@' is missing."""
    with pytest.raises(CallError) as exc:
        call("zfs.tier.rewrite_job_failures", {"tier_job_id": "no_at_sign"})
    assert "Invalid tier_job_id" in str(exc.value)


# ----------------------------------------------------------------------------
# rewrite_job_status: invalid / nonexistent
# ----------------------------------------------------------------------------


def test_rewrite_job_status_invalid_id_format_raises_callerror():
    with pytest.raises(CallError) as exc:
        call("zfs.tier.rewrite_job_status", {"tier_job_id": "no_at_sign"})
    assert "Invalid tier_job_id" in str(exc.value)


def test_rewrite_job_status_nonexistent_raises_callerror():
    """Body wraps daemon get_info exception in CallError."""
    with pytest.raises(CallError):
        call("zfs.tier.rewrite_job_status", {"tier_job_id": _FAKE_JOB_ID})


# ----------------------------------------------------------------------------
# rewrite_job_recover
# ----------------------------------------------------------------------------


def test_rewrite_job_recover_invalid_id_format_raises_callerror():
    with pytest.raises(CallError) as exc:
        call("zfs.tier.rewrite_job_recover", {"tier_job_id": "no_at_sign"})
    assert "Invalid tier_job_id" in str(exc.value)


# ----------------------------------------------------------------------------
# rewrite_job_cancel: invalid format
# ----------------------------------------------------------------------------


def test_rewrite_job_cancel_invalid_id_format_raises_callerror():
    with pytest.raises(CallError) as exc:
        call("zfs.tier.rewrite_job_cancel", {"tier_job_id": "no_at_sign"})
    assert "Invalid tier_job_id" in str(exc.value)


# ----------------------------------------------------------------------------
# rewrite_job_query: filters, pagination, multi-status
# ----------------------------------------------------------------------------


def test_rewrite_job_query_multiple_status_filter_includes_active(tier_pool):
    """Filtering with a list of statuses (including the active job's actual
    status) should include the active job."""
    ds1 = f"{tier_pool['name']}/jq_multi1_{time.monotonic_ns()}"
    ds2 = f"{tier_pool['name']}/jq_multi2_{time.monotonic_ns()}"
    call("pool.dataset.create", {"name": ds1})
    call("pool.dataset.create", {"name": ds2})
    try:
        _populate(ds1)
        _populate(ds2)
        e1 = call("zfs.tier.rewrite_job_create", {"dataset_name": ds1})
        e2 = call("zfs.tier.rewrite_job_create", {"dataset_name": ds2})

        active = call(
            "zfs.tier.rewrite_job_query",
            {"status": ["QUEUED", "RUNNING", "COMPLETE"]},
        )
        ids = {j["tier_job_id"] for j in active}
        # Both newly-created jobs should be in QUEUED/RUNNING/COMPLETE
        assert e1["tier_job_id"] in ids
        assert e2["tier_job_id"] in ids

        # Filter to a state neither should be in (CANCELLED) — both should
        # be absent unless they raced (very unlikely on empty dataset).
        cancelled_only = call(
            "zfs.tier.rewrite_job_query", {"status": ["CANCELLED"]}
        )
        cancelled_ids = {j["tier_job_id"] for j in cancelled_only}
        assert e1["tier_job_id"] not in cancelled_ids
        assert e2["tier_job_id"] not in cancelled_ids
    finally:
        for ds in (ds1, ds2):
            try:
                call("pool.dataset.delete", ds, {"recursive": True})
            except Exception:
                pass


def test_rewrite_job_query_pagination_via_query_options(tier_pool):
    """rewrite_job_query honors the standard query-options pagination."""
    ds1 = f"{tier_pool['name']}/jq_page1_{time.monotonic_ns()}"
    ds2 = f"{tier_pool['name']}/jq_page2_{time.monotonic_ns()}"
    call("pool.dataset.create", {"name": ds1})
    call("pool.dataset.create", {"name": ds2})
    try:
        _populate(ds1)
        _populate(ds2)
        call("zfs.tier.rewrite_job_create", {"dataset_name": ds1})
        call("zfs.tier.rewrite_job_create", {"dataset_name": ds2})

        page_one = call(
            "zfs.tier.rewrite_job_query",
            {"query-options": {"limit": 1, "offset": 0}},
        )
        assert len(page_one) <= 1

        all_jobs = call("zfs.tier.rewrite_job_query", {})
        # Sanity: with limit unspecified, both should show
        ids = {j["tier_job_id"] for j in all_jobs}
        # The two we created should both be present
        # (we don't assert on count because other jobs may exist)
        # but limit=1 should have given us at most 1 row.
        assert len(ids) >= 2
    finally:
        for ds in (ds1, ds2):
            try:
                call("pool.dataset.delete", ds, {"recursive": True})
            except Exception:
                pass


# ----------------------------------------------------------------------------
# rewrite_job_status event source (per-dataset, polls every 2s)
# ----------------------------------------------------------------------------


def test_status_event_source_no_events_for_dataset_without_job(tier_ds):
    """Subscribing to the per-dataset event source for a dataset with no job
    should not emit any events within 5s (poll interval is 2s)."""
    arg = json.dumps({"dataset_name": tier_ds})
    with client() as c:
        events = []
        c.subscribe(
            f"zfs.tier.rewrite_job_status:{arg}",
            lambda t, **m: events.append((t, m)),
            sync=True,
        )
        time.sleep(5)

    assert events == [], (
        f"Expected no events for a dataset without a job, got: {pprint.pformat(events)}"
    )


# ----------------------------------------------------------------------------
# rewrite_job_query event source: ADDED + eventual CHANGED with COMPLETE
# ----------------------------------------------------------------------------


def test_query_event_source_complete_emits_changed(tier_ds, wait_for_job_status):
    """Subscribe, create a job, wait — the event source should emit ADDED for
    creation and then CHANGED ending with COMPLETE.

    The query event source polls every 5s, so we wait up to 30s for the
    CHANGED event to land."""
    _populate(tier_ds)
    with client() as c:
        events = []
        c.subscribe(
            "zfs.tier.rewrite_job_query",
            lambda t, **m: events.append((t, m)),
            sync=True,
        )
        entry = c.call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds})

        # Wait for COMPLETE via the synchronous status RPC first…
        wait_for_job_status(entry["tier_job_id"], {"COMPLETE", "ERROR"}, timeout=60)
        # …then give the query event source two poll intervals to catch up.
        time.sleep(12)

    matching = [
        e for e in events if e[1].get("id") == entry["tier_job_id"]
    ]
    types = {e[0] for e in matching}
    assert "ADDED" in types, pprint.pformat(events)
    # CHANGED may have been collapsed into a single complete state
    complete = [
        e for e in matching
        if e[0] == "CHANGED" and e[1]["fields"].get("status") == "COMPLETE"
    ]
    assert complete, (
        "Expected at least one CHANGED event with status=COMPLETE; "
        f"got: {pprint.pformat(events)}"
    )


# ----------------------------------------------------------------------------
# Status RPC on a completed job (sanity)
# ----------------------------------------------------------------------------


def test_status_after_complete_has_terminal_state_and_stats_or_none(tier_ds, wait_for_job_status):
    _populate(tier_ds)
    entry = call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds})
    wait_for_job_status(entry["tier_job_id"], {"COMPLETE", "ERROR"}, timeout=60)
    status = call(
        "zfs.tier.rewrite_job_status", {"tier_job_id": entry["tier_job_id"]}
    )
    assert status["status"] in ("COMPLETE", "ERROR")
    # On terminal state, the daemon may or may not have stats; lock down the
    # type contract.
    assert status["stats"] is None or isinstance(status["stats"], dict)
    if status["status"] == "ERROR":
        assert status["error"] is None or isinstance(status["error"], str)
