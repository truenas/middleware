from collections import defaultdict

from middlewared.utils.zfs import query_imported_fast_impl

from .utils import safely_retrieve_dimension


def get_pool_stats(netdata_metrics: dict) -> dict:
    data = defaultdict(lambda: {'available': None, 'used': None, 'total': None})
    pool_data = query_imported_fast_impl()

    for dimension_name, value in safely_retrieve_dimension(netdata_metrics, 'truenas_pool.usage').items():
        value = value or {}
        pool_guid, stat_key = dimension_name.split('.')
        data[pool_data[pool_guid]['name']][stat_key] = value
    return data
