from .utils import normalize_value, safely_retrieve_dimension


def get_arc_stats(netdata_metrics: dict) -> dict:
    data = {
        'arc_max_size': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'zfs.arc_size', 'max', 0), multiplier=1024 * 1024,
        ),
        'arc_size': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'zfs.arc_size', 'size', 0), multiplier=1024 * 1024,
        ),
        'arc_demand_data_hits': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'zfs.demand_data_hits', 'hits', 0)
        ),
        'arc_prefetch_data_hits': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'zfs.prefetch_data_hits', 'hits', 0)
        ),
        'arc_demand_metadata_hits': 0,
        'arc_prefetch_metadata_hits': 0,
        'cache_hit_ratio': 0.0,
    }
    hits = safely_retrieve_dimension(netdata_metrics, 'zfs.hits', 'hits', 0)
    misses = safely_retrieve_dimension(netdata_metrics, 'zfs.hits', 'misses', 0)
    data['arc_demand_metadata_hits'] = normalize_value(safely_retrieve_dimension(
        netdata_metrics, 'zfs.dhits', 'hits', 0
    ) - data['arc_demand_data_hits'])
    data['arc_prefetch_metadata_hits'] = normalize_value(safely_retrieve_dimension(
        netdata_metrics, 'zfs.phits', 'hits', 0
    ) - data['arc_prefetch_data_hits'])

    if total := (hits + misses):
        data['cache_hit_ratio'] = hits / total

    return data
