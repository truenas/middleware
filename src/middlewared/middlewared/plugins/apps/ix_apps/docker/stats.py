from collections import defaultdict

from .utils import get_docker_client, PROJECT_KEY


def list_resources_stats_by_project(project_name: str | None = None) -> dict:
    projects = defaultdict(lambda: {
        'cpu_usage': 0,
        'memory_stats': 0,
        'networks': defaultdict(lambda: {'rx_bytes': 0, 'tx_bytes': 0}),
        'blkio_stats': {'read': 0, 'write': 0},
    })
    with get_docker_client() as client:
        label_filter = {'label': f'{PROJECT_KEY}={project_name}' if project_name else PROJECT_KEY}
        for container in client.containers.list(all=True, filters=label_filter, sparse=False):
            stats = container.stats(stream=False, decode=None, one_shot=True)
            project = container.labels.get(PROJECT_KEY)
            if not project:
                continue

            blkio_container_stats = stats.get('blkio_stats', {}).get('io_service_bytes_recursive') or {}
            project_stats = projects[project]
            project_stats['cpu_usage'] += stats.get('cpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0)
            project_stats['memory_stats'] += stats.get('memory_stats', {}).get('usage', 0)
            for entry in filter(lambda x: x['op'] in ('read', 'write'), blkio_container_stats):
                project_stats['blkio_stats'][entry['op']] += entry['value']
            for net_name, net_values in stats.get('networks', {}).items():
                project_stats['networks'][net_name]['rx_bytes'] += net_values.get('rx_bytes', 0)
                project_stats['networks'][net_name]['tx_bytes'] += net_values.get('tx_bytes', 0)

    return projects
