from collections import defaultdict
import concurrent.futures
from typing import Any, TypedDict, cast

from .utils import get_docker_client, PROJECT_KEY


class BlkioStats(TypedDict):
    read: int
    write: int


class NetworkStats(TypedDict):
    rx_bytes: int
    tx_bytes: int


class ResourceStats(TypedDict):
    cpu_usage: int
    memory: int
    networks: dict[str, NetworkStats]
    blkio: BlkioStats


def get_default_stats() -> dict[str, ResourceStats]:
    """Returns the default dictionary structure for project stats."""
    return defaultdict(lambda: {
        'cpu_usage': 0,
        'memory': 0,
        'networks': defaultdict(lambda: {'rx_bytes': 0, 'tx_bytes': 0}),
        'blkio': {'read': 0, 'write': 0},
    })


def _parse_blkio(stats: dict[str, Any]) -> BlkioStats:
    """Parses Block IO stats, accumulating read/write values."""
    result: BlkioStats = {'read': 0, 'write': 0}
    raw_blkio = stats.get('blkio_stats', {}).get('io_service_bytes_recursive') or []
    if isinstance(raw_blkio, list):
        for entry in raw_blkio:
            op = entry.get('op')
            if op in ('read', 'write'):
                result[op] += int(entry.get('value', 0))
    return result


def _parse_networks(stats: dict[str, Any]) -> dict[str, NetworkStats]:
    """Parses Network stats."""
    parsed: dict[str, NetworkStats] = {}
    raw_networks = cast(dict[str, Any], stats.get('networks') or {})
    for name, values in raw_networks.items():
        net_entry: NetworkStats = {
            'rx_bytes': int(values.get('rx_bytes', 0)),
            'tx_bytes': int(values.get('tx_bytes', 0))
        }
        parsed[name] = net_entry
    return parsed


def get_container_stats(container: Any) -> tuple[str, ResourceStats] | None:
    """
    Extract resource usage stats for a single Docker container.
    """
    try:
        project = container.attrs.get('Labels', {}).get(PROJECT_KEY)
        if not project:
            return None
        stats = container.stats(stream=False, decode=None, one_shot=True)
        container_stats: ResourceStats = {
            'cpu_usage': int(stats.get('cpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0)),
            'memory': int(stats.get('memory_stats', {}).get('usage', 0)),
            'blkio': _parse_blkio(stats),
            'networks': _parse_networks(stats),
        }
        return project, container_stats
    except Exception:
        return None


def list_resources_stats_by_project(project_name: str | None = None) -> dict[str, ResourceStats]:
    projects = get_default_stats()
    label_filter = {
        'label': f'{PROJECT_KEY}={project_name}' if project_name else PROJECT_KEY
    }
    with get_docker_client() as client:
        containers = list(client.containers.list(all=True, filters=label_filter, sparse=True))
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(get_container_stats, container) 
                for container in containers
            ]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if not result:
                    continue
                project, stats = result
                p_stats = projects[project]
                p_stats['cpu_usage'] += stats['cpu_usage']
                p_stats['memory'] += stats['memory']
                p_stats['blkio']['read'] += stats['blkio']['read']
                p_stats['blkio']['write'] += stats['blkio']['write']
                for net_name, net_stats in stats['networks'].items():
                    p_stats['networks'][net_name]['rx_bytes'] += net_stats['rx_bytes']
                    p_stats['networks'][net_name]['tx_bytes'] += net_stats['tx_bytes']
    return dict(projects)
