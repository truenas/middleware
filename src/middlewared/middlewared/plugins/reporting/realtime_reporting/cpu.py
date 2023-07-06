from .utils import safely_retrieve_dimension


def get_cpu_core_stats(netdata_metrics: dict, core_number: int = None, chart_name: str = None) -> dict:
    chart = f'cpu.cpu{core_number}' if core_number is not None else chart_name
    data = {
        'user': safely_retrieve_dimension(netdata_metrics, chart, 'user', 0),
        'nice': safely_retrieve_dimension(netdata_metrics, chart, 'nice', 0),
        'system': safely_retrieve_dimension(netdata_metrics, chart, 'system', 0),
        'idle': safely_retrieve_dimension(netdata_metrics, chart, 'idle', 0),
        'iowait': safely_retrieve_dimension(netdata_metrics, chart, 'iowait', 0),
        'irq': safely_retrieve_dimension(netdata_metrics, chart, 'irq', 0),
        'softirq': safely_retrieve_dimension(netdata_metrics, chart, 'softirq', 0),
        'steal': safely_retrieve_dimension(netdata_metrics, chart, 'steal', 0),
        'guest': safely_retrieve_dimension(netdata_metrics, chart, 'guest', 0),
        'guest_nice': safely_retrieve_dimension(netdata_metrics, chart, 'guest_nice', 0),
        'usage': 0,
    }
    if cp_total := sum(data.values()):
        # usage is the sum of all but idle and iowait
        data['usage'] = ((cp_total - data['idle'] - data['iowait']) / cp_total) * 100

    return data


def get_all_cores_stats(netdata_metrics: dict, cores: int) -> dict:
    data = {}
    for core_num in range(cores):
        data[str(core_num)] = get_cpu_core_stats(netdata_metrics, core_num)
    return data


def get_cpu_stats(netdata_metrics: dict, cores: int) -> dict:
    return {
        **({str(core_num): get_cpu_core_stats(netdata_metrics, core_num) for core_num in range(cores)}),
        'average': get_cpu_core_stats(netdata_metrics, chart_name='system.cpu'),
    }
