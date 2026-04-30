import time

import pytest

from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call, client


# Expected topology of `reporting.realtime.stats` (and the matching
# `reporting.realtime` event payload). Mirrors `ReportingRealtimeEventSourceEvent`
# in src/middlewared/middlewared/api/v27_0_0/reporting.py.
#
# Top-level keys are fixed. Sub-keys are fixed for memory / zfs / disks. Sub-keys
# for cpu / interfaces / pools are host-dependent (per-core, per-interface,
# per-pool) and validated separately against system.cpu_info / interface.query /
# pool.query.
EXPECTED_STATS_TOPOLOGY: dict[str, frozenset[str] | None] = {
    "cpu": None,
    "disks": frozenset(
        {
            "busy",
            "read_bytes",
            "write_bytes",
            "read_ops",
            "write_ops",
        }
    ),
    "interfaces": None,
    "memory": frozenset(
        {
            "arc_size",
            "arc_free_memory",
            "arc_available_memory",
            "physical_memory_total",
            "physical_memory_available",
        }
    ),
    "pools": None,
    "zfs": frozenset(
        {
            "demand_accesses_per_second",
            "demand_data_accesses_per_second",
            "demand_metadata_accesses_per_second",
            "demand_data_hits_per_second",
            "demand_data_io_hits_per_second",
            "demand_data_misses_per_second",
            "demand_data_hit_percentage",
            "demand_data_io_hit_percentage",
            "demand_data_miss_percentage",
            "demand_metadata_hits_per_second",
            "demand_metadata_io_hits_per_second",
            "demand_metadata_misses_per_second",
            "demand_metadata_hit_percentage",
            "demand_metadata_io_hit_percentage",
            "demand_metadata_miss_percentage",
            "l2arc_hits_per_second",
            "l2arc_misses_per_second",
            "total_l2arc_accesses_per_second",
            "l2arc_access_hit_percentage",
            "l2arc_miss_percentage",
            "bytes_read_per_second_from_the_l2arc",
            "bytes_written_per_second_to_the_l2arc",
        }
    ),
}

EXPECTED_TOP_LEVEL_KEYS = frozenset(EXPECTED_STATS_TOPOLOGY)
EXPECTED_CPU_PER_CORE_KEYS = frozenset({"usage", "temp"})


def _collect_one_event(c, timeout=8):
    events = []

    def callback(type_, **message):
        events.append((type_, message.get("fields") or {}))

    c.subscribe("reporting.realtime", callback, sync=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not events:
        time.sleep(0.5)
    assert events, "no reporting.realtime event received within timeout"
    return events[0][1]


def _assert_matches_topology(payload, label):
    assert payload.keys() == EXPECTED_TOP_LEVEL_KEYS, (
        f"{label}: {payload.keys() ^ EXPECTED_TOP_LEVEL_KEYS}"
    )
    for top_key, expected_subkeys in EXPECTED_STATS_TOPOLOGY.items():
        if expected_subkeys is None:
            # Host-dependent block — only assert it's a dict here.
            assert isinstance(payload[top_key], dict), f"{label}.{top_key}"
            continue
        assert payload[top_key].keys() == expected_subkeys, (
            f"{label}.{top_key}: {payload[top_key].keys() ^ expected_subkeys}"
        )


@pytest.fixture(scope="module")
def realtime_event():
    with client() as c:
        return _collect_one_event(c)


def test_reporting_realtime():
    with unprivileged_user_client(["REPORTING_READ"]) as c:
        events = []

        def callback(type, **message):
            events.append((type, message))

        c.subscribe("reporting.realtime", callback, sync=True)

        time.sleep(5)

        assert events


def test_realtime_event_topology(realtime_event):
    _assert_matches_topology(realtime_event, "event")


def test_realtime_event_memory_values(realtime_event):
    memory = realtime_event["memory"]
    for key, value in memory.items():
        assert isinstance(value, int) and value >= 0, f"{key}: {value!r}"
    assert memory["physical_memory_total"] > 0


def test_realtime_event_zfs_values(realtime_event):
    for key, value in realtime_event["zfs"].items():
        assert value >= 0, f"{key}: {value!r}"


def test_realtime_event_disks_values(realtime_event):
    for key, value in realtime_event["disks"].items():
        assert isinstance(value, (int, float)) and value >= 0, f"{key}: {value!r}"


def test_realtime_event_cpu_keys(realtime_event):
    core_count = call("system.cpu_info")["core_count"]
    expected = frozenset({"cpu"} | {f"cpu{i}" for i in range(core_count)})
    assert realtime_event["cpu"].keys() == expected
    for core, sub in realtime_event["cpu"].items():
        assert sub.keys() == EXPECTED_CPU_PER_CORE_KEYS


def test_realtime_event_matches_internal_stats_call():
    """
    Cross-check: `reporting.realtime.stats` is the private synchronous RPC the
    event source itself drives. Calling it directly and subscribing to the
    event must produce the same payload structure with consistent values for
    stable fields (physical_memory_total, top-level keys).

    Per-second rate fields drift between the two reads, so we only assert
    structural equivalence and exactness on values that don't change at runtime.
    """
    stats = call("reporting.realtime.stats")
    assert stats, "reporting.realtime.stats returned empty (netdata down?)"

    with client() as c:
        event = _collect_one_event(c)

    _assert_matches_topology(stats, "stats")
    _assert_matches_topology(event, "event")
    assert event["cpu"].keys() == stats["cpu"].keys()
    assert (
        event["memory"]["physical_memory_total"]
        == stats["memory"]["physical_memory_total"]
    )


def test_realtime_pool_keys_match_pool_query(realtime_event):
    pool_names = frozenset(pool["name"] for pool in call("pool.query"))
    if not pool_names:
        pytest.skip("no imported pools — cannot validate event pool keys")
    unexpected = realtime_event["pools"].keys() - pool_names
    assert not unexpected, f"event reported pools not in pool.query: {unexpected}"
    for pool_name, sub in realtime_event["pools"].items():
        # pool.py:18 filters out falsy values, so any visible stat must be truthy
        for stat_key, value in sub.items():
            assert value, f"{pool_name}.{stat_key}: {value!r}"
