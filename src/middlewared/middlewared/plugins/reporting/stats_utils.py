from middlewared.utils.cpu import cpu_info


def get_kubernetes_pods_stats(pod_names: list, netdata_metrics: dict) -> dict:
    k3s_stats_dimensions = {
        netdata_metrics['labels'][i]: netdata_metrics['data'][-1][i]
        for i in range(len(netdata_metrics['labels']))
    }

    stats = {'memory': 0, 'cpu': 0, 'network': {'incoming': 0, 'outgoing': 0}}
    for pod_name in pod_names:
        stats['cpu'] += int(k3s_stats_dimensions.get(f'{pod_name}.cpu', 0))
        stats['memory'] += int(k3s_stats_dimensions.get(f'{pod_name}.mem', 0))
        stats['network']['incoming'] += int(k3s_stats_dimensions.get(f'{pod_name}.net.incoming', 0))
        stats['network']['outgoing'] += int(k3s_stats_dimensions.get(f'{pod_name}.net.outgoing', 0))

    # Convert CPU usage from nanocores to percentage of total available CPU power across all cores.
    stats['cpu'] = ((stats['cpu'] / 1000000000) / cpu_info()['core_count']) * 100
    return stats
