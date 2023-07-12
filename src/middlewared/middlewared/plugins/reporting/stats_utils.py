from middlewared.utils.cpu import cpu_info

from .realtime_reporting.utils import normalize_value, safely_retrieve_dimension


def get_kubernetes_pods_stats(pod_names: list, netdata_metrics: dict) -> dict:
    stats = {'memory': 0, 'cpu': 0, 'network': {'incoming': 0, 'outgoing': 0}}
    for pod_name in pod_names:
        stats['cpu'] += int(safely_retrieve_dimension(
            netdata_metrics, f'k3s_stats.{pod_name}.cpu', f'{pod_name}.cpu', default=0
        ))
        stats['memory'] += normalize_value(int(safely_retrieve_dimension(
            netdata_metrics, f'k3s_stats.{pod_name}.mem', f'{pod_name}.mem', default=0
        )), divisor=1024 * 1024)  # Convert bytes to megabytes.
        stats['network']['incoming'] += safely_retrieve_dimension(
            netdata_metrics, f'k3s_stats.{pod_name}.net', f'{pod_name}.net.incoming', default=0
        )
        stats['network']['outgoing'] += safely_retrieve_dimension(
            netdata_metrics, f'k3s_stats.{pod_name}.net', f'{pod_name}.net.outgoing', default=0
        )

    # Convert CPU usage from nanocores to percentage of total available CPU power across all cores.
    stats['cpu'] = ((stats['cpu'] / 1000000000) / cpu_info()['core_count']) * 100
    return stats
