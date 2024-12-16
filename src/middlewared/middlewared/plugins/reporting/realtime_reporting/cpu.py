from .utils import safely_retrieve_dimension


def calculate_usage(cpu_stats: dict) -> float:
    cp_total = sum(cpu_stats.values())
    return ((cp_total - cpu_stats['idle'] - cpu_stats['iowait']) / cp_total) * 100 if cp_total else 0


def get_cpu_stats(netdata_metrics: dict) -> dict:
    metric_name = 'system.cpu'
    fields = ['user', 'nice', 'system', 'idle', 'iowait', 'irq', 'softirq', 'steal', 'guest', 'guest_nice']
    data = {field: safely_retrieve_dimension(netdata_metrics, metric_name, field, 0) for field in fields}
    data['usage'] = calculate_usage(data)
    return data
