from .utils import normalize_value, safely_retrieve_dimension


def get_arc_stats(netdata_metrics: dict) -> dict:
    data = {
        'arc_max_size': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'zfs.arc_size', 'max', 0), multiplier=1024 * 1024,
        ),
        'arc_size': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'zfs.arc_size', 'size', 0), multiplier=1024 * 1024,
        ),
        'cache_hit_ratio': 0.0,
    }
    hits = safely_retrieve_dimension(netdata_metrics, 'zfs.hits', 'hits', 0)
    misses = safely_retrieve_dimension(netdata_metrics, 'zfs.hits', 'misses', 0)

    if total := (hits + misses):
        data['cache_hit_ratio'] = hits / total

    return data
