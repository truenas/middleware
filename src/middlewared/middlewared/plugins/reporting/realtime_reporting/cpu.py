from middlewared.utils.cpu import cpu_info
from .utils import safely_retrieve_dimension


def get_cpu_stats(netdata_metrics: dict) -> dict:
    data = {
        'cpu': {
            'usage': safely_retrieve_dimension(
                netdata_metrics, f'truenas_cpu_usage.cpu', 'cpu', 0
            ),
            'temp': safely_retrieve_dimension(
                netdata_metrics, 'cputemp.temperatures', 'cpu',
            ) or None
        }}
    for core_index in range(cpu_info()['core_count']):
        data[f'cpu{core_index}'] = {
            'usage': safely_retrieve_dimension(
                netdata_metrics, f'truenas_cpu_usage.cpu', f'cpu{core_index}', 0
            ),
            'temp': safely_retrieve_dimension(
                netdata_metrics, 'cputemp.temperatures', f'cpu{core_index}',
            ) or None
        }

    return data
