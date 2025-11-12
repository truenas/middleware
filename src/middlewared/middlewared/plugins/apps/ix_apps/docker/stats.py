from collections import defaultdict

import requests

from .utils import get_docker_client, PROJECT_KEY


def get_default_stats():
    return defaultdict(lambda: {
        'cpu_usage': 0,
        'memory': 0,
        'networks': defaultdict(lambda: {'rx_bytes': 0, 'tx_bytes': 0}),
        'blkio': {'read': 0, 'write': 0},
    })


def list_resources_stats_by_project(project_name: str | None = None) -> dict:
    retries = 2
    while retries > 0:
        # We do this because when an app is being stopped, we can run into a race condition
        # where the container got listed but when we queried it's stats we were not able
        # to get them as the container by that time had been nuked (this is similar to what we
        # do when we list resources by project)
        try:
            return list_resources_stats_by_project_internal(project_name)
        except requests.exceptions.HTTPError:
            retries -= 1
            if retries == 0:
                raise


def list_resources_stats_by_project_internal(project_name: str | None = None) -> dict:
    projects = get_default_stats()
    with get_docker_client() as client:
        # List all containers to include external apps
        # If a specific project_name is requested, we'll filter below
        for container in client.containers.list(all=True, sparse=False):
            # Get project key from label, or use container name for external containers
            project = container.labels.get(PROJECT_KEY, container.attrs.get('Name', '').lstrip('/'))
            if not project:
                continue

            # If a specific project was requested, filter to only that project
            if project_name and project != project_name:
                continue

            stats = container.stats(stream=False, decode=None, one_shot=True)
            blkio_container_stats = stats.get('blkio_stats', {}).get('io_service_bytes_recursive') or {}
            project_stats = projects[project]
            project_stats['cpu_usage'] += stats.get('cpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0)
            project_stats['memory'] += stats.get('memory_stats', {}).get('usage', 0)
            for entry in filter(lambda x: x['op'] in ('read', 'write'), blkio_container_stats):
                project_stats['blkio'][entry['op']] += entry['value']
            for net_name, net_values in stats.get('networks', {}).items():
                project_stats['networks'][net_name]['rx_bytes'] += net_values.get('rx_bytes', 0)
                project_stats['networks'][net_name]['tx_bytes'] += net_values.get('tx_bytes', 0)

    return projects
