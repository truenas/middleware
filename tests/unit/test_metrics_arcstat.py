import pytest

from truenas_pylibzfs import kstat

from middlewared.utils.metrics.arcstat import (
    ArcStatDescriptions,
    calculate_arc_stats_impl,
    get_arc_stats,
)


# Attributes consumed by calculate_arc_demand_stats_impl, calculate_l2arc_stats_impl
# and calculate_arc_stats_impl. If `truenas_pylibzfs.kstat.ArcStats` ever drops or
# renames any of these, the upstream rename must come with a coordinated middleware
# update.
KSTAT_REQUIRED_ATTRS = (
    'memory_free_bytes',
    'memory_available_bytes',
    'size',
    'demand_data_hits',
    'demand_metadata_hits',
    'demand_data_iohits',
    'demand_metadata_iohits',
    'demand_data_misses',
    'demand_metadata_misses',
    'l2_size',
    'l2_hits',
    'l2_misses',
    'l2_read_bytes',
    'l2_write_bytes',
)

PERCENT_KEYS = frozenset({'ddh%', 'ddi%', 'ddm%', 'dmh%', 'dmi%', 'dmm%', 'l2hit%', 'l2miss%'})


def test_get_arc_stats_runs():
    """Direct regression guard for the import bug fixed in bbe0e4."""
    assert get_arc_stats()


def test_get_arc_stats_keys_match_descriptions():
    assert get_arc_stats().keys() == ArcStatDescriptions.keys()


def test_get_arc_stats_value_shape():
    for key, value in get_arc_stats().items():
        assert isinstance(value, tuple) and len(value) == 2, f'{key}: {value!r}'
        numeric, description = value
        assert isinstance(numeric, (int, float)), f'{key}: numeric is {type(numeric)}'
        assert description == ArcStatDescriptions[key]


def test_get_arc_stats_size_invariants():
    stats = get_arc_stats()
    for key in ('free', 'avail', 'size'):
        numeric, _ = stats[key]
        assert isinstance(numeric, int)
    # A live ARC always holds something
    assert stats['size'][0] > 0
    # Cumulative-derived rates should never be negative
    for key in ('dread', 'ddread', 'dmread', 'l2read', 'l2bytes', 'l2wbytes'):
        assert stats[key][0] >= 0, f'{key}: {stats[key][0]!r}'
    for key in PERCENT_KEYS:
        assert 0 <= stats[key][0] <= 100, f'{key}: {stats[key][0]!r}'


def test_get_arc_stats_demand_percentages_sum():
    """When the read counter is non-zero the three percent components sum to 100."""
    raw_stats = calculate_arc_stats_impl(kstat.get_arcstats(), 1)
    if raw_stats['ddread'][0] > 0:
        total = raw_stats['ddh%'][0] + raw_stats['ddi%'][0] + raw_stats['ddm%'][0]
        assert abs(total - 100) <= 0.5
    if raw_stats['dmread'][0] > 0:
        total = raw_stats['dmh%'][0] + raw_stats['dmi%'][0] + raw_stats['dmm%'][0]
        assert abs(total - 100) <= 0.5
    if raw_stats['l2read'][0] > 0:
        total = raw_stats['l2hit%'][0] + raw_stats['l2miss%'][0]
        assert abs(total - 100) <= 0.5


@pytest.mark.parametrize('intv', [1, 2, 5])
def test_get_arc_stats_intv(intv):
    stats = get_arc_stats(intv)
    assert stats.keys() == ArcStatDescriptions.keys()
    for key in PERCENT_KEYS:
        assert 0 <= stats[key][0] <= 100


@pytest.mark.parametrize('attr', KSTAT_REQUIRED_ATTRS)
def test_kstat_get_arcstats_attrs(attr):
    """
    Asserts that every attribute the calculation helpers reach for is present
    on the live kstat.ArcStats object. Catches regressions like the one in
    bbe0e4 where the import surface of truenas_pylibzfs.kstat changed.
    """
    snapshot = kstat.get_arcstats()
    assert hasattr(snapshot, attr), f'kstat.ArcStats is missing {attr!r}'
    assert isinstance(getattr(snapshot, attr), int)
