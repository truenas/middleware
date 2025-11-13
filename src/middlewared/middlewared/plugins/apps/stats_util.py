from middlewared.utils.cpu import cpu_info

from .ix_apps.metadata import get_collective_metadata
from .ix_apps.utils import get_app_name_from_project_name

NANO_SECOND = 1000000000


def normalize_projects_stats(all_projects_stats: dict, old_stats: dict, interval: int) -> list[dict]:
    normalized_projects_stats = []
    all_configured_apps = get_collective_metadata()
    for project, data in all_projects_stats.items():
        app_name = get_app_name_from_project_name(project)
        if app_name not in all_configured_apps:
            continue
        else:
            all_configured_apps.pop(app_name)

        normalized_data = {
            'app_name': app_name,
            'memory': data['memory'],
            'blkio': data['blkio'],
        }

        # Docker provides CPU usage time in nanoseconds.
        # To calculate the CPU usage percentage:
        # 1. Calculate the difference in CPU usage (`cpu_delta`) between the current and previous stats.
        # 2. Normalize this delta over the given time interval by dividing by (interval * NANO_SECOND).
        # 3. Multiply by 100 to convert to percentage.
        cpu_delta = data['cpu_usage'] - old_stats[project]['cpu_usage']
        if cpu_delta >= 0:
            normalized_data['cpu_usage'] = (cpu_delta / (interval * NANO_SECOND * cpu_info()['core_count'])) * 100
        else:
            # This will happen when there were multiple containers and an app is being stopped
            # and old stats contain cpu usage times of multiple containers and current stats
            # only contains the stats of the containers which are still running which means collectively
            # current cpu usage time will be obviously low then what old stats contain
            normalized_data['cpu_usage'] = 0

        networks = []
        for net_name, network_data in data['networks'].items():
            networks.append({
                'interface_name': net_name,
                'rx_bytes': int(
                    (network_data['rx_bytes'] - old_stats[project]['networks'][net_name]['rx_bytes']) / interval
                ),
                'tx_bytes': int(
                    (network_data['tx_bytes'] - old_stats[project]['networks'][net_name]['tx_bytes']) / interval
                ),
            })
        normalized_data['networks'] = networks
        normalized_projects_stats.append(normalized_data)

    for stopped_app in all_configured_apps:
        normalized_projects_stats.append({
            'app_name': stopped_app,
            'memory': 0,
            'cpu_usage': 0,
            'networks': [],
            'blkio': {'read': 0, 'write': 0},
        })

    return normalized_projects_stats
