from .utils import get_docker_client, PROJECT_KEY


def list_resources_stats_by_project(project_name: str) -> dict:
    with get_docker_client() as client:
        label_filter = {'label': f'{PROJECT_KEY}={project_name}' if project_name else PROJECT_KEY}
        stats = {}
        for container in client.containers.list(all=True, filters=label_filter, sparse=False):
            cont_stats = container.stats(stream=False, decode=None)
            stats[cont_stats['name'].strip('/')] = {
                'cpu_usage': cont_stats.get('cpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0),
                'memory_stats': cont_stats.get('memory_stats', {}).get('usage', 0),
                'networks': {
                    net_name: {
                        'rx_bytes': net_values['rx_bytes'],
                        'tx_bytes': net_values['tx_bytes']
                    } for net_name, net_values in cont_stats.get('networks', {}).items()
                },
                'blkio_stats': {
                    blkio['op']: blkio['value']
                    for blkio in cont_stats.get('blkio_stats', {}).get('io_service_bytes_recursive', {}) or {}
                }
            }
        return stats
