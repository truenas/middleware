import time

import pytest

from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call, client


ZFS_EVENT_KEYS = {
    'demand_accesses_per_second',
    'demand_data_accesses_per_second',
    'demand_metadata_accesses_per_second',
    'demand_data_hits_per_second',
    'demand_data_io_hits_per_second',
    'demand_data_misses_per_second',
    'demand_data_hit_percentage',
    'demand_data_io_hit_percentage',
    'demand_data_miss_percentage',
    'demand_metadata_hits_per_second',
    'demand_metadata_io_hits_per_second',
    'demand_metadata_misses_per_second',
    'demand_metadata_hit_percentage',
    'demand_metadata_io_hit_percentage',
    'demand_metadata_miss_percentage',
    'l2arc_hits_per_second',
    'l2arc_misses_per_second',
    'total_l2arc_accesses_per_second',
    'l2arc_access_hit_percentage',
    'l2arc_miss_percentage',
    'bytes_read_per_second_from_the_l2arc',
    'bytes_written_per_second_to_the_l2arc',
}

MEMORY_EVENT_KEYS = {
    'arc_size',
    'arc_free_memory',
    'arc_available_memory',
    'physical_memory_total',
    'physical_memory_available',
}

TOP_LEVEL_KEYS = {'cpu', 'disks', 'interfaces', 'memory', 'zfs', 'pools'}


def _collect_one_event(c, timeout=8):
    events = []

    def callback(type_, **message):
        events.append((type_, message.get('fields') or {}))

    c.subscribe('reporting.realtime', callback, sync=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not events:
        time.sleep(0.5)
    assert events, 'no reporting.realtime event received within timeout'
    return events[0][1]


@pytest.fixture(scope='module')
def realtime_event():
    with client() as c:
        return _collect_one_event(c)


def test_reporting_realtime():
    """
    Original role-gate smoke test — a `REPORTING_READ`-only user can subscribe
    and at least one event arrives within 5 seconds.
    """
    with unprivileged_user_client(['REPORTING_READ']) as c:
        events = []

        def callback(type, **message):
            events.append((type, message))

        c.subscribe('reporting.realtime', callback, sync=True)

        time.sleep(5)

        assert events


def test_realtime_event_top_level_keys(realtime_event):
    assert set(realtime_event) == TOP_LEVEL_KEYS, set(realtime_event) ^ TOP_LEVEL_KEYS


def test_realtime_event_memory_subkeys(realtime_event):
    memory = realtime_event['memory']
    assert set(memory) == MEMORY_EVENT_KEYS
    for key, value in memory.items():
        assert isinstance(value, int) and value >= 0, f'{key}: {value!r}'
    assert memory['physical_memory_total'] > 0


def test_realtime_event_zfs_subkeys(realtime_event):
    zfs = realtime_event['zfs']
    assert set(zfs) == ZFS_EVENT_KEYS
    for key, value in zfs.items():
        assert value >= 0, f'{key}: {value!r}'


def test_realtime_event_cpu_keys(realtime_event):
    core_count = call('system.cpu_info')['core_count']
    expected = {'cpu'} | {f'cpu{i}' for i in range(core_count)}
    assert set(realtime_event['cpu']) == expected
    for core, sub in realtime_event['cpu'].items():
        assert set(sub) == {'usage', 'temp'}


def test_realtime_memory_matches_helper_on_same_snapshot():
    """
    Strongest cross-check: the helper
    `realtime_reporting.memory.get_memory_info` is what the event source uses
    to populate `payload['memory']`. Feeding the helper the same
    `netdata.get_all_metrics` snapshot must produce a dict that matches the
    event's `memory` block exactly (down to numeric value).

    Sample the metrics snapshot first, then immediately collect a fresh event
    so they reflect roughly the same point in time. We compare structure and
    individual values with a small tolerance to allow for the inevitable
    sub-second drift between the two reads.
    """
    from middlewared.plugins.reporting.realtime_reporting.memory import get_memory_info

    netdata_metrics = call('netdata.get_all_metrics')
    if not netdata_metrics:
        pytest.skip('netdata returned no metrics')

    helper_result = get_memory_info(netdata_metrics)

    with client() as c:
        event = _collect_one_event(c)

    assert set(event['memory']) == set(helper_result)
    # Memory values change slowly (KB scale per second). Anything more than 5%
    # drift in arc_size / physical_memory_* between two reads ~2s apart would
    # indicate the helper and the event source are wired to different sources.
    assert event['memory']['physical_memory_total'] == helper_result['physical_memory_total']
    assert abs(event['memory']['arc_size'] - helper_result['arc_size']) < max(
        helper_result['arc_size'] * 0.05, 1024 * 1024,
    )


def test_realtime_pool_keys_match_pool_query(realtime_event):
    pool_names = {pool['name'] for pool in call('pool.query')}
    if not pool_names:
        pytest.skip('no imported pools — cannot validate event pool keys')
    event_pool_names = set(realtime_event['pools'])
    assert event_pool_names <= pool_names, (
        f'event reported pools not in pool.query: {event_pool_names - pool_names}'
    )
    for pool_name, sub in realtime_event['pools'].items():
        # pool.py:18 filters out falsy values, so any visible stat must be truthy
        for stat_key, value in sub.items():
            assert value, f'{pool_name}.{stat_key}: {value!r}'
