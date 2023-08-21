import asyncio

from aiohttp.client_exceptions import ClientConnectorError
from collections import defaultdict
from enum import Enum

from bases.FrameworkServices.SimpleService import SimpleService

from middlewared.plugins.kubernetes_linux.k8s.core_api import Node
from middlewared.plugins.kubernetes_linux.k8s.exceptions import ApiException


class StatsTypes(Enum):
    NETWORK = 'net'
    CPU = 'cpu'
    MEMORY = 'mem'


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.update_every = 1
        self.k3s_prefix = 'k3s_stat'

    def check(self):
        return True

    def get_dimension_name(self, pod_name, stat_type):
        return f'{pod_name}.{stat_type}'

    def get_chart_options_base(self, chart_name):
        return [chart_name, 'k3s_pod_stats', 'Pods Resource usage']

    def add_cpu_chart(self, pod_name, state_type=StatsTypes.CPU.value):
        self.charts[self.name].add_dimension([self.get_dimension_name(pod_name, state_type)])

    def add_net_chart(self, pod_name, state_type=StatsTypes.NETWORK.value):
        self.charts[self.name].add_dimension([f'{self.get_dimension_name(pod_name, state_type)}.incoming'])
        self.charts[self.name].add_dimension([f'{self.get_dimension_name(pod_name, state_type)}.outgoing'])

    def add_mem_chart(self, pod_name, state_type=StatsTypes.MEMORY.value):
        self.charts[self.name].add_dimension([self.get_dimension_name(pod_name, state_type)])

    def gather_pod_stat(self, pod_stats, data):
        pod_name = pod_stats['podRef']['name']
        data[self.get_dimension_name(pod_name, StatsTypes.CPU.value)] = int(pod_stats['cpu']['usageNanoCores'])
        data[self.get_dimension_name(pod_name, StatsTypes.MEMORY.value)] = int(pod_stats['memory']['rssBytes'])
        for interface in pod_stats['network']['interfaces']:
            data[f'{self.get_dimension_name(pod_name, StatsTypes.NETWORK.value)}.incoming'] += int(interface['rxBytes'])
            data[f'{self.get_dimension_name(pod_name, StatsTypes.NETWORK.value)}.outgoing'] += int(interface['txBytes'])

    def prepare_pods_charts(self, pod_stats):
        self.charts.charts.clear()
        self.charts.add_chart(
            self.get_chart_options_base(self.name) + [
                'K3s Pods stats', 'k3s_status', 'Pods resource usage', 'k3s stats', 'line'
            ]
        )
        for pod_stat in pod_stats:
            self.add_cpu_chart(pod_stat)
            self.add_mem_chart(pod_stat)
            self.add_net_chart(pod_stat)

    def _get_data(self):
        try:
            pods_stats = asyncio.run(Node.get_stats())['pods']
        except (ClientConnectorError, ApiException):
            return {}
        data = defaultdict(int)
        self.prepare_pods_charts([pod['podRef']['name'] for pod in pods_stats])
        for pod_stat in pods_stats:
            self.gather_pod_stat(pod_stat, data)
        return data
