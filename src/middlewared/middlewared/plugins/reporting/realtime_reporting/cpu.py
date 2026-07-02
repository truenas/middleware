from middlewared.utils.cpu import cpu_info
from .utils import safely_retrieve_dimension


def get_cpu_stats(netdata_metrics: dict) -> dict:
    cinfo = cpu_info()
    data = {
        'cpu': {
            'usage': safely_retrieve_dimension(
                netdata_metrics, 'truenas_cpu_usage.cpu', 'cpu', 0
            ),
            'temp': safely_retrieve_dimension(
                netdata_metrics, 'cputemp.temperatures', 'cpu',
            ) or None
        }}
    # Iterate the real online logical CPU ids: netdata omits offline/isolated
    # cpus from both the usage and temperature charts, and get_cpu_temperatures
    # keys on those same ids. Fall back to a dense range when topology is
    # unreadable and logical_to_phys is empty.
    for core_index in sorted(cinfo['logical_to_phys']) or range(cinfo['core_count'] or 0):
        data[f'cpu{core_index}'] = {
            'usage': safely_retrieve_dimension(
                netdata_metrics, 'truenas_cpu_usage.cpu', f'cpu{core_index}', 0
            ),
            'temp': safely_retrieve_dimension(
                netdata_metrics, 'cputemp.temperatures', f'cpu{core_index}',
            ) or None
        }

    return data
