from collections import defaultdict
import concurrent.futures

from .utils import get_docker_client, PROJECT_KEY


def get_default_stats():
    return defaultdict(lambda: {
        'cpu_usage': 0,
        'memory': 0,
        'networks': defaultdict(lambda: {'rx_bytes': 0, 'tx_bytes': 0}),
        'blkio': {'read': 0, 'write': 0},
    })


def get_container_stats(container):
    """
    Extract resource usage stats for a single Docker container.
    """
    try:
        stats = container.stats(stream=False, decode=None, one_shot=True)
        project = container.attrs.get('Labels', {}).get(PROJECT_KEY)
        if not project:
            return None
        container_stats = {
            'cpu_usage': 0,
            'memory': 0,
            'blkio': {'read': 0, 'write': 0},
            'networks': {}
        }
        cpu_stats = stats.get('cpu_stats', {})
        container_stats['cpu_usage'] = cpu_stats.get('cpu_usage', {}).get('total_usage', 0)
        mem_stats = stats.get('memory_stats', {})
        container_stats['memory'] = mem_stats.get('usage', 0)
        blkio_stats = stats.get('blkio_stats', {}).get('io_service_bytes_recursive') or []
        if isinstance(blkio_stats, list):
            for entry in filter(lambda x: x.get('op') in ('read', 'write'), blkio_stats):
                container_stats['blkio'][entry['op']] += entry.get('value', 0)
        for net_name, net_values in stats.get('networks', {}).items():
            container_stats['networks'][net_name] = {
                'rx_bytes': net_values.get('rx_bytes', 0),
                'tx_bytes': net_values.get('tx_bytes', 0)
            }
        return project, container_stats
    except Exception:
        return None


def list_resources_stats_by_project(project_name: str | None = None) -> dict:
    projects = get_default_stats()
    with get_docker_client() as client:
        label_filter = {'label': f'{PROJECT_KEY}={project_name}' if project_name else PROJECT_KEY}
        containers = list(client.containers.list(all=True, filters=label_filter, sparse=True))
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_container_stats, container) for container in containers]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    project, stats = result
                    project_stats = projects[project]
                    project_stats['cpu_usage'] += stats['cpu_usage']
                    project_stats['memory'] += stats['memory']
                    for op in ['read', 'write']:
                        project_stats['blkio'][op] += stats['blkio'][op]
                    for net_name, net_stats in stats['networks'].items():
                        project_stats['networks'][net_name]['rx_bytes'] += net_stats['rx_bytes']
                        project_stats['networks'][net_name]['tx_bytes'] += net_stats['tx_bytes']

    return projects
