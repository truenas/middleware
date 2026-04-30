"""
Live tests for plugins.reporting.realtime_reporting.* helpers.

Each helper consumes a `netdata_metrics` dict produced by
`netdata.get_all_metrics`; we feed in real netdata data *and* an empty dict to
exercise the `safely_retrieve_dimension` defensive paths.
"""
import glob

import pytest

from truenas_api_client import Client

from middlewared.plugins.reporting.realtime_reporting.arcstat import get_arc_stats
from middlewared.plugins.reporting.realtime_reporting.cgroup import get_cgroup_stats
from middlewared.plugins.reporting.realtime_reporting.cpu import get_cpu_stats
from middlewared.plugins.reporting.realtime_reporting.ifstat import get_interface_stats
from middlewared.plugins.reporting.realtime_reporting.iostat import get_disk_stats
from middlewared.plugins.reporting.realtime_reporting.memory import get_memory_info
from middlewared.plugins.reporting.realtime_reporting.pool import get_pool_stats
from middlewared.utils.cpu import cpu_info
from middlewared.utils.disks import get_disk_names
from middlewared.utils.disks_.disk_class import iterate_disks


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

ZFS_PERCENT_KEYS = {k for k in ZFS_EVENT_KEYS if k.endswith('_percentage')}

MEMORY_EVENT_KEYS = {
    'arc_size',
    'arc_free_memory',
    'arc_available_memory',
    'physical_memory_total',
    'physical_memory_available',
}

DISK_EVENT_KEYS = {'read_ops', 'read_bytes', 'write_ops', 'write_bytes', 'busy'}


@pytest.fixture(scope='module')
def netdata_metrics():
    with Client(private_methods=True) as c:
        data = c.call('netdata.get_all_metrics')
    if not data:
        pytest.skip('netdata returned no metrics — service may be down or warming up')
    return data


@pytest.fixture(scope='module')
def interface_names():
    with Client(private_methods=True) as c:
        return [
            iface['name'] for iface in c.call(
                'interface.query', [], {'extra': {'retrieve_names_only': True}}
            )
        ]


# --- get_arc_stats ----------------------------------------------------------


def test_arc_stats_empty_dict_safe():
    result = get_arc_stats({})
    assert set(result) == ZFS_EVENT_KEYS
    for key, value in result.items():
        assert value == 0, f'{key}: {value!r}'


def test_arc_stats_live_shape(netdata_metrics):
    result = get_arc_stats(netdata_metrics)
    assert set(result) == ZFS_EVENT_KEYS
    for key, value in result.items():
        assert isinstance(value, (int, float)), f'{key}: {type(value).__name__}'
        assert value >= 0, f'{key}: {value!r}'
    for key in ZFS_PERCENT_KEYS:
        assert result[key] <= 100, f'{key}: {result[key]!r}'


# --- get_memory_info --------------------------------------------------------


def test_memory_empty_dict_safe():
    result = get_memory_info({})
    assert set(result) == MEMORY_EVENT_KEYS
    for key, value in result.items():
        assert value == 0, f'{key}: {value!r}'


def test_memory_live_shape(netdata_metrics):
    result = get_memory_info(netdata_metrics)
    assert set(result) == MEMORY_EVENT_KEYS
    for key, value in result.items():
        assert isinstance(value, (int, float)), f'{key}: {type(value).__name__}'
        assert value >= 0, f'{key}: {value!r}'
    assert result['physical_memory_total'] > 0
    assert result['physical_memory_total'] >= result['physical_memory_available']
    assert result['arc_size'] > 0


# --- get_cpu_stats ----------------------------------------------------------


def _expected_cpu_keys():
    return {'cpu'} | {f'cpu{i}' for i in range(cpu_info()['core_count'])}


def test_cpu_empty_dict_safe():
    result = get_cpu_stats({})
    assert set(result) == _expected_cpu_keys()
    for core, sub in result.items():
        assert set(sub) == {'usage', 'temp'}, f'{core}: {set(sub)!r}'
        assert sub['usage'] == 0
        assert sub['temp'] is None


def test_cpu_live_shape(netdata_metrics):
    result = get_cpu_stats(netdata_metrics)
    assert set(result) == _expected_cpu_keys()
    for core, sub in result.items():
        assert set(sub) == {'usage', 'temp'}
        assert isinstance(sub['usage'], (int, float))
        assert 0 <= sub['usage'] <= 100, f'{core}: usage={sub["usage"]!r}'
        assert sub['temp'] is None or isinstance(sub['temp'], (int, float))


# --- get_disk_stats ---------------------------------------------------------


def test_disk_empty_inputs_safe():
    result = get_disk_stats({}, [], {})
    assert set(result) == DISK_EVENT_KEYS
    for key, value in result.items():
        assert value == 0, f'{key}: {value!r}'


def test_disk_live_shape(netdata_metrics):
    disks = get_disk_names()
    disk_mapping = {entry.name: entry.identifier for entry in iterate_disks()}
    result = get_disk_stats(netdata_metrics, disks, disk_mapping)
    assert set(result) == DISK_EVENT_KEYS
    for key, value in result.items():
        assert isinstance(value, (int, float)), f'{key}: {type(value).__name__}'
        assert value >= 0, f'{key}: {value!r}'


# --- get_interface_stats ----------------------------------------------------


def test_interface_empty_inputs_safe():
    result = get_interface_stats({}, [])
    assert dict(result) == {}


def test_interface_live_shape(netdata_metrics, interface_names):
    if not interface_names:
        pytest.skip('no network interfaces reported by interface.query')
    result = get_interface_stats(netdata_metrics, interface_names)
    assert set(result) == set(interface_names)
    for name, sub in result.items():
        assert sub['link_state'] in ('LINK_STATE_UP', 'LINK_STATE_DOWN'), \
            f'{name}: {sub["link_state"]!r}'
        assert isinstance(sub['speed'], (int, float)) and sub['speed'] >= 0
        assert isinstance(sub['received_bytes_rate'], (int, float))
        assert isinstance(sub['sent_bytes_rate'], (int, float))
        assert sub['received_bytes_rate'] >= 0
        assert sub['sent_bytes_rate'] >= 0


# --- get_pool_stats ---------------------------------------------------------


def test_pool_empty_dict_safe():
    result = get_pool_stats({})
    assert dict(result) == {}


def test_pool_live_shape(netdata_metrics):
    """
    The unit-test environment has no imported data pools so the returned dict
    is allowed to be empty — we only assert the *shape* of any entries.
    """
    result = get_pool_stats(netdata_metrics)
    for pool_name, sub in result.items():
        assert isinstance(pool_name, str) and pool_name
        assert isinstance(sub, dict)
        for stat_key, value in sub.items():
            assert isinstance(stat_key, str)
            # pool.py:18 filters out falsy values, so anything we see must
            # be truthy — typically a positive int byte-count.
            assert value


# --- get_cgroup_stats -------------------------------------------------------


def test_cgroup_empty_inputs_safe():
    assert dict(get_cgroup_stats({}, [])) == {}


def test_cgroup_live_runs(netdata_metrics):
    """
    Heuristic for cgroup names mirrors the metric-count approximation used in
    plugins/reporting/rest.py — every *.service cgroup file becomes a candidate.
    The helper may legitimately return an empty dict on a host with no
    container/vm services, but it must not crash.
    """
    cgroups = sorted({
        path.rsplit('/', 1)[-1].removesuffix('.service')
        for path in glob.glob('/sys/fs/cgroup/**/*.service', recursive=True)
    })
    result = get_cgroup_stats(netdata_metrics, cgroups)
    for cgroup_name, sub in result.items():
        assert isinstance(cgroup_name, str)
        assert isinstance(sub, dict)
        for metric_name, context in sub.items():
            assert isinstance(metric_name, str)
            assert isinstance(context, dict)
