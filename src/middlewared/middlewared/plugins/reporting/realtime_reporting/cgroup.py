import collections
import typing


def get_cgroup_stats(netdata_metrics: dict, cgroups: typing.List[str]) -> dict[str, dict]:
    data = collections.defaultdict(dict)
    cgroup_keys = list(filter(lambda x: x.startswith('cgroup_'), netdata_metrics.keys()))

    for cgroup in cgroups:
        for i in filter(lambda x: x.startswith(f'cgroup_{cgroup}.'), cgroup_keys):
            name = i.split('.', 1)[-1]
            context = data[cgroup][name] = {}
            metric = netdata_metrics[i]
            unit = metric["units"].lower()
            unit = unit.replace('/', '_')
            for dimension, value in metric['dimensions'].items():
                dimension = dimension.replace(' ', '_')
                context[f'{name}_{dimension}_{unit}'] = value['value']

    return data
