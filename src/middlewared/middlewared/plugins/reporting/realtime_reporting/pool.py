from collections import defaultdict

from .utils import safely_retrieve_dimension


def get_pool_stats(netdata_metrics: dict) -> dict:
    data = defaultdict(lambda: {'available': None, 'used': None})

    for dimension_name, value in safely_retrieve_dimension(netdata_metrics, 'truenas_pool.usage').items():
        pool_name, stat_key = dimension_name.split('.')
        data[pool_name][stat_key] = value
    return data
