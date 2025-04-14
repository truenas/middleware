from collections import defaultdict

from middlewared.utils.zfs import query_imported_fast_impl

from .utils import safely_retrieve_dimension


def get_pool_stats(netdata_metrics: dict) -> dict:
    data = defaultdict(dict)
    pool_data = query_imported_fast_impl()
    for dimension_name, value in (
        safely_retrieve_dimension(netdata_metrics, "truenas_pool.usage") or {}
    ).items():
        # this data eventually gets reported to our reporting.realtime
        # subscription and so the UI team does not want us to send
        # events with empty data. We only want to report on pools for
        # which we're able to retrieve data from.
        if value:
            pool_guid, stat_key = dimension_name.split(".")
            try:
                data[pool_data[pool_guid]["name"]].update({stat_key: value})
            except KeyError:
                continue
    return data
