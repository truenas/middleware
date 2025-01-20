from .utils import normalize_value, safely_retrieve_dimension


def get_memory_info(netdata_metrics: dict) -> dict:

    return {
        'arc_size': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.size', 'size', 0),
        ),
        'arc_free_memory': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.free', 'free', 0),
        ),
        'arc_available_memory': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.avail', 'avail', 0),
        ),
        'physical_memory_total': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_meminfo.total', 'total', 0),
        ),
        'physical_memory_available': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_meminfo.available', 'available', 0),
        ),
    }
