import typing

from .graph_base import GraphBase


class CPUPlugin(GraphBase):

    title = 'CPU Usage'
    vertical_label = '%CPU'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.cpu'

    def query_parameters(self) -> dict:
        return super().query_parameters() | {
            'dimensions': 'system|user|idle|softirq|nice|iowait',
        }


class CPUTempPlugin(GraphBase):

    title = 'CPU Temperature'
    vertical_label = 'Celsius'

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return 'cputemp.temperatures'


class DISKPlugin(GraphBase):

    title = 'Disk I/O Bandwidth'
    vertical_label = 'Kibibytes/s'

    async def get_identifiers(self) -> typing.Optional[list]:
        disks = {f'disk.{disk["name"]}' for disk in await self.middleware.call('disk.query')}
        return [disk.rsplit('.')[-1] for disk in (disks & set(await self.all_charts()))]

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return f'disk.{identifier}'


class InterfacePlugin(GraphBase):

    title = 'Interface Traffic'
    vertical_label = 'Kilobits/s'

    async def get_identifiers(self) -> typing.Optional[list]:
        ifaces = {f'net.{i["name"]}' for i in await self.middleware.call('interface.query')}
        return [iface.split('.')[-1] for iface in (ifaces & set(await self.all_charts()))]

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return f'net.{identifier}'


class LoadPlugin(GraphBase):

    title = 'System Load Average'
    vertical_label = 'Processes'

    LOAD_MAPPING = {
        'load1': 'shortterm',
        'load5': 'midterm',
        'load15': 'longterm',
    }

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.load'

    def normalize_metrics(self, metrics) -> dict:
        metrics = super().normalize_metrics(metrics)
        metrics['legend'] = [self.LOAD_MAPPING.get(legend, legend) for legend in metrics['legend']]
        return metrics


class MemoryPlugin(GraphBase):

    title = 'Physical memory utilization'
    vertical_label = 'Mebibytes/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.ram'


class NFSStatPlugin(GraphBase):

    title = 'NFS input/output stats'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'nfsd.io'


class ProcessesPlugin(GraphBase):

    title = 'System Processes State'
    vertical_label = 'Processes'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.processes_state'

    def query_parameters(self) -> dict:
        return super().query_parameters() | {
            'dimensions': 'running|sleeping_uninterruptible|sleeping_interruptible|stopped|zombie',
        }


class SwapPlugin(GraphBase):

    title = 'Swap Utilization'
    vertical_label = 'Mebibytes/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.swap'

    def query_parameters(self) -> dict:
        return super().query_parameters() | {
            'dimensions': 'used|free',
        }


class UptimePlugin(GraphBase):

    title = 'System Uptime'
    vertical_label = 'Seconds'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.uptime'

# TODO: Revisit these zfs plugins and see the maximum parity we can achieve with old stats
#  we were collecting


class ARCActualRatePlugin(GraphBase):

    title = 'ZFS Actual Cache Hits Rate'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'zfs.actual_hits_rate'


class ARCRatePlugin(GraphBase):

    title = 'ZFS ARC Hits Rate'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'zfs.hits_rate'


class ARCSizePlugin(GraphBase):

    title = 'ZFS ARC Size'
    vertical_label = 'Mebibytes'

    LABEL_MAPPING = {
        'arcsz': 'arc_size',
    }

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'zfs.arc_size'

    def query_parameters(self) -> dict:
        return super().query_parameters() | {
            'dimensions': 'arcsz',
        }

    def normalize_metrics(self, metrics) -> dict:
        metrics = super().normalize_metrics(metrics)
        metrics['legend'] = [self.LABEL_MAPPING.get(legend, legend) for legend in metrics['legend']]
        return metrics


class ARCResultPlugin(GraphBase):

    title = 'ZFS ARC Result'
    vertical_label = 'Percentage'

    IDENTIFIER_MAPPING = {
        'demand_data': 'zfs.demand_data_hits',
        'prefetch_data': 'zfs.prefetch_data_hits',
    }

    async def get_identifiers(self) -> typing.Optional[list]:
        return list(self.IDENTIFIER_MAPPING.keys())

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return self.IDENTIFIER_MAPPING[identifier]
