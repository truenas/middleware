from middlewared.utils.cpu import cpu_info
from .utils import safely_retrieve_dimension


def calculate_usage(cpu_stats: dict) -> float:
    cp_total = sum(cpu_stats.values())
    return ((cp_total - cpu_stats['idle'] - cpu_stats['iowait']) / cp_total) * 100 if cp_total else 0


def get_cpu_stats(netdata_metrics: dict) -> dict:
    metric_name = 'system.cpu'
    fields = ['user', 'nice', 'system', 'idle', 'iowait', 'irq', 'softirq', 'steal', 'guest', 'guest_nice']
    data = {field: safely_retrieve_dimension(netdata_metrics, metric_name, field, 0) for field in fields}
    data['aggregated_usage'] = safely_retrieve_dimension(netdata_metrics, 'truenas_cpu_usage.cpu', 'cpu', 0)
    for core_index in range(cpu_info()['core_count']):
        data[f'core{core_index}_usage'] = safely_retrieve_dimension(
            netdata_metrics, f'truenas_cpu_usage.cpu{core_index}', f'cpu{core_index}', 0
        )
    return data
