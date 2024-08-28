from .ix_apps.utils import get_app_name_from_project_name


NANO_SECOND = 1000000000


def normalize_projects_stats(all_projects_stats: dict, old_stats: dict, interval: int) -> list[dict]:
    normalized_projects_stats = []
    for project, data in all_projects_stats.items():
        data['app_name'] = get_app_name_from_project_name(project)

        # Docker provides CPU usage time in nanoseconds.
        # To calculate the CPU usage percentage:
        # 1. Calculate the difference in CPU usage (`cpu_delta`) between the current and previous stats.
        # 2. Normalize this delta over the given time interval by dividing by (interval * NANO_SECOND).
        # 3. Multiply by 100 to convert to percentage.
        cpu_delta = data['cpu_usage'] - old_stats[project]['cpu_usage']
        data['cpu_usage'] = (cpu_delta / (interval * NANO_SECOND)) * 100

        networks = []
        for net_name, net_data in data['networks'].items():
            net_data['interface_name'] = net_name
            # calculate networks received/transmitted bytes/s
            net_data['rx_bytes'] = int(
                (net_data['rx_bytes'] - old_stats[project]['networks'][net_name]['rx_bytes']) / interval
            )
            net_data['tx_bytes'] = int(
                (net_data['tx_bytes'] - old_stats[project]['networks'][net_name]['tx_bytes']) / interval
            )
            networks.append(net_data)
        data['networks'] = networks
        normalized_projects_stats.append(data)
    return normalized_projects_stats
