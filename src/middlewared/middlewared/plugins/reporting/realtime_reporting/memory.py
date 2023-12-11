import humanfriendly

from .utils import normalize_value, safely_retrieve_dimension


def get_memory_info(netdata_metrics: dict) -> dict:
    with open('/proc/meminfo') as f:
        meminfo = {
            s[0]: humanfriendly.parse_size(s[1], binary=True)
            for s in [
                line.split(':', 1)
                for line in f.readlines()
            ]
        }

    classes = {
        'page_tables': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'mem.kernel', 'PageTables', 0), multiplier=1024 * 1024,
        ),
        'swap_cache': normalize_value(meminfo['SwapCached'], multiplier=1024),
        'slab_cache': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'mem.kernel', 'Slab', 0), multiplier=1024 * 1024,
        ),
        'cache': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'system.ram', 'cached', 0), multiplier=1024 * 1024,
        ),
        'buffers': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'system.ram', 'buffers', 0), multiplier=1024 * 1024,
        ),
        'unused': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'system.ram', 'free', 0), multiplier=1024 * 1024,
        ),
        'arc': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'zfs.arc_size', 'size', 0), multiplier=1024 * 1024,
        ),
        'apps': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'system.ram', 'used', 0), multiplier=1024 * 1024,
        ),
    }

    extra = {
        'inactive': normalize_value(meminfo['Inactive'], multiplier=1024),
        'committed': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'mem.committed', 'Committed_AS', 0), multiplier=1024 * 1024,
        ),
        'active': normalize_value(meminfo['Active'], multiplier=1024),
        'vmalloc_used': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'mem.kernel', 'VmallocUsed', 0), multiplier=1024 * 1024,
        ),
        'mapped': normalize_value(meminfo['Mapped'], multiplier=1024),
    }

    swap = {
        'used': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'system.swap', 'used', 0), multiplier=1024 * 1024,
        ),
        'total': normalize_value(meminfo['SwapTotal'], multiplier=1024),
    }

    return {
        'classes': classes,
        'extra': extra,
        'swap': swap,
    }
