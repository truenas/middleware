import typing

from middlewared.utils.disks import get_disks_for_temperature_reading

from .graph_base import GraphBase


class CPUPlugin(GraphBase):

    title = 'CPU Usage'
    uses_identifiers = False
    vertical_label = '%CPU'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.cpu'

    def query_parameters(self) -> dict:
        return super().query_parameters() | {
            'dimensions': 'system|user|idle|softirq|nice|iowait',
        }


class CPUTempPlugin(GraphBase):

    title = 'CPU Temperature'
    uses_identifiers = False
    vertical_label = 'Celsius'
    skip_zero_values_in_aggregation = True

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return 'cputemp.temperatures'


class DISKPlugin(GraphBase):

    title = 'Disk I/O Bandwidth'
    vertical_label = 'Kibibytes/s'

    def get_title(self):
        return 'Disk I/O ({identifier})'

    async def get_identifiers(self) -> typing.Optional[list]:
        disks = {f'disk.{disk["name"]}' for disk in await self.middleware.call('disk.query')}
        return [disk.rsplit('.')[-1] for disk in (disks & set(await self.all_charts()))]

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return f'disk.{identifier}'

    def normalize_metrics(self, metrics) -> dict:
        metrics = super().normalize_metrics(metrics)
        if len(metrics['legend']) < 3:
            for to_add in {'time', 'reads', 'writes'} - set(metrics['legend']):
                metrics['legend'].append(to_add)

        write_column = metrics['legend'].index('writes')
        for index, data in enumerate(metrics['data']):
            data_length = len(data)
            if data_length < 3:
                for i in range(3 - data_length):
                    data.append(0)

            if data[write_column] is not None:
                metrics['data'][index][write_column] = abs(data[write_column])
        return metrics


class InterfacePlugin(GraphBase):

    title = 'Interface Traffic'
    vertical_label = 'Kilobits/s'

    def get_title(self):
        return 'Interface Traffic ({identifier})'

    async def get_identifiers(self) -> typing.Optional[list]:
        ifaces = {f'net.{i["name"]}' for i in await self.middleware.call('interface.query')}
        return [iface.split('.')[-1] for iface in (ifaces & set(await self.all_charts()))]

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return f'net.{identifier}'

    def normalize_metrics(self, metrics) -> dict:
        metrics = super().normalize_metrics(metrics)
        if len(metrics['legend']) < 3:
            for to_add in {'time', 'received', 'sent'} - set(metrics['legend']):
                metrics['legend'].append(to_add)

        sent_column = metrics['legend'].index('sent')
        for index, data in enumerate(metrics['data']):
            data_length = len(data)
            if data_length < 3:
                for i in range(3 - data_length):
                    data.append(0)

            if data[sent_column] is not None:
                metrics['data'][index][sent_column] = abs(data[sent_column])
        return metrics


class LoadPlugin(GraphBase):

    title = 'System Load Average'
    uses_identifiers = False
    vertical_label = 'Load'

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


class ProcessesPlugin(GraphBase):

    title = 'System Active Processes'
    uses_identifiers = False
    vertical_label = 'Processes'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.active_processes'


class MemoryPlugin(GraphBase):

    title = 'Physical memory utilization'
    uses_identifiers = False
    vertical_label = 'Mebibytes'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.ram'


class SwapPlugin(GraphBase):

    title = 'Swap Utilization'
    uses_identifiers = False
    vertical_label = 'Mebibytes'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.swap'

    def query_parameters(self) -> dict:
        return super().query_parameters() | {
            'dimensions': 'used|free',
        }


class UptimePlugin(GraphBase):

    title = 'System Uptime'
    uses_identifiers = False
    vertical_label = 'Seconds'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.uptime'

# TODO: Revisit these zfs plugins and see the maximum parity we can achieve with old stats
#  we were collecting


class ARCActualRatePlugin(GraphBase):

    title = 'ZFS Actual Cache Hits Rate'
    uses_identifiers = False
    vertical_label = 'Events/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'zfs.actual_hits_rate'


class ARCRatePlugin(GraphBase):

    title = 'ZFS ARC Hits Rate'
    uses_identifiers = False
    vertical_label = 'Events/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'zfs.hits_rate'


class ARCSizePlugin(GraphBase):

    title = 'ZFS ARC Size'
    uses_identifiers = False
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


class DiskTempPlugin(GraphBase):

    title = 'Disks Temperature'
    vertical_label = 'Celsius'
    disk_mapping = {}
    skip_zero_values_in_aggregation = True

    def get_title(self):
        return 'Disk Temperature {identifier}'

    async def build_context(self):
        self.disk_mapping = {}
        all_charts = await self.all_charts()
        for disk in (await self.middleware.run_in_thread(get_disks_for_temperature_reading)).values():
            identifier = disk.id if disk.id.startswith('nvme') else disk.serial
            for k in (identifier, identifier.replace('-', '_')):
                if f'smart_log_smart.disktemp.{k}' in all_charts:
                    self.disk_mapping[disk.id] = k
                    break

    async def get_identifiers(self) -> typing.Optional[list]:
        return list(self.disk_mapping.keys())

    def normalize_metrics(self, metrics) -> dict:
        metrics = super().normalize_metrics(metrics)

        if len(metrics['legend']) < 2:
            for to_add in {'time', 'temperature_value'} - set(metrics['legend']):
                metrics['legend'].append(to_add)
        else:
            metrics['legend'][1] = 'temperature_value'

        return metrics

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return f'smart_log_smart.disktemp.{self.disk_mapping[identifier]}'


class UPSBase(GraphBase):

    UPS_IDENTIFIER = None

    async def export_multiple_identifiers(
        self, query_params: dict, identifiers: list, aggregate: bool = True
    ) -> typing.List[dict]:
        self.UPS_IDENTIFIER = (await self.middleware.call('ups.config'))['identifier']
        return await super().export_multiple_identifiers(query_params, identifiers, aggregate)


class UPSChargePlugin(UPSBase):

    title = 'UPS Charging'
    vertical_label = 'Percentage'
    uses_identifiers = False

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return f'nut_{self.UPS_IDENTIFIER}.charge'


class UPSRuntimePlugin(UPSBase):

    title = 'UPS Runtime'
    vertical_label = 'Seconds'
    uses_identifiers = False

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return f'nut_{self.UPS_IDENTIFIER}.runtime'


class UPSVoltagePlugin(UPSBase):

    title = 'UPS Voltage'
    vertical_label = 'Volts'

    IDENTIFIER_MAPPING = {
        'battery': 'battery_voltage',
        'input': 'input_voltage',
        'output': 'output_voltage'
    }

    async def get_identifiers(self) -> typing.Optional[list]:
        return list(self.IDENTIFIER_MAPPING.keys())

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return f'nut_{self.UPS_IDENTIFIER}.{self.IDENTIFIER_MAPPING[identifier]}'


class UPSCurrentPlugin(UPSBase):

    title = 'UPS Input Current'
    vertical_label = 'Ampere'
    uses_identifiers = False

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return f'nut_{self.UPS_IDENTIFIER}.input_current'


class UPSFrequencyPlugin(UPSBase):

    title = 'UPS Input Frequency'
    vertical_label = 'Hz'
    uses_identifiers = False

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return f'nut_{self.UPS_IDENTIFIER}.input_frequency'


class UPSLoadPlugin(UPSBase):

    title = 'UPS Input Load'
    vertical_label = 'Percentage'
    uses_identifiers = False

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return f'nut_{self.UPS_IDENTIFIER}.load'


class UPSTemperaturePlugin(UPSBase):

    title = 'UPS Temperature'
    vertical_label = 'Temperature'
    skip_zero_values_in_aggregation = True
    uses_identifiers = False

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return f'nut_{self.UPS_IDENTIFIER}.temp'
