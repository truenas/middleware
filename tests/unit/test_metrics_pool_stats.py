from middlewared.utils.metrics.pool_stats import get_pool_dataset_stats
from middlewared.utils.zfs import query_imported_fast_impl


def test_get_pool_dataset_stats_shape():
    """Boot pool is always imported on TrueNAS, so the result is non-empty."""
    stats = get_pool_dataset_stats()
    assert stats, 'expected at least the boot pool'
    for guid, values in stats.items():
        assert isinstance(guid, str) and guid.isdigit(), f'{guid!r} is not a numeric GUID'
        assert set(values) >= {'used', 'avail'}, f'{guid}: {values!r}'
        assert isinstance(values['used'], int) and values['used'] >= 0
        assert isinstance(values['avail'], int) and values['avail'] >= 0


def test_get_pool_dataset_stats_includes_boot_pool():
    """
    The unit-test environment has no imported data pools (only boot-pool). The
    helper must still produce results — direct guard for the no-data-pool case.
    """
    imported_guids = set(query_imported_fast_impl())
    stats = get_pool_dataset_stats()
    # Every pool reported by the kstat-based fast query should appear in the
    # zfs-list-derived stats.
    assert imported_guids <= set(stats), (
        f'kstat-imported guids {imported_guids - set(stats)} missing from stats'
    )
