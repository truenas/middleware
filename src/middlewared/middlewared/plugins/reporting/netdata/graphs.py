import typing

from middlewared.utils.disks_.disk_class import iterate_disks

from .graph_base import GraphBase
from .utils import get_human_disk_name


class CPUPlugin(GraphBase):

    title = 'CPU Usage'
    uses_identifiers = False
    vertical_label = '%CPU'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_cpu_usage.cpu'


class CPUTempPlugin(GraphBase):

    title = 'CPU Temperature'
    uses_identifiers = False
    vertical_label = 'Celsius'
    skip_zero_values_in_aggregation = True

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return 'cputemp.temperatures'


class MemoryPlugin(GraphBase):

    title = 'Physical memory available'
    uses_identifiers = False
    vertical_label = 'Bytes'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_meminfo.available'


class DISKPlugin(GraphBase):

    title = 'Disk I/O Bandwidth'
    vertical_label = 'Kibibytes/s'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.disk_mapping = {}

    def get_title(self):
        return 'Disk I/O ({identifier})'

    async def build_context(self):
        all_charts = await self.all_charts()
        self.disk_mapping = await self.middleware.run_in_thread(self.get_mapping, all_charts)

    def get_mapping(self, all_charts):
        return {
            get_human_disk_name(disk): disk.identifier for disk in iterate_disks()
            if f'truenas_disk_stats.io.{disk.identifier}' in all_charts
        }

    async def get_identifiers(self) -> typing.Optional[list]:
        return list(self.disk_mapping.keys())

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return f'truenas_disk_stats.io.{self.disk_mapping[identifier]}'


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


class UptimePlugin(GraphBase):

    title = 'System Uptime'
    uses_identifiers = False
    vertical_label = 'Seconds'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.uptime'


class ARCFreeMemoryPlugin(GraphBase):
    title = 'ARC Free Memory'
    uses_identifiers = False
    vertical_label = 'bytes'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.free'


class ARCAvailableMemoryPlugin(GraphBase):
    title = 'ARC Available Memory'
    uses_identifiers = False
    vertical_label = 'bytes'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.avail'


class ARCSizePlugin(GraphBase):
    title = 'ARC Size'
    uses_identifiers = False
    vertical_label = 'bytes'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.size'


class DemandAccessesPerSecondPlugin(GraphBase):
    title = 'Demand Accesses per Second'
    uses_identifiers = False
    vertical_label = 'accesses/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.dread'


class DemandDataAccessesPerSecondPlugin(GraphBase):
    title = 'Demand Data Accesses per Second'
    uses_identifiers = False
    vertical_label = 'accesses/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.ddread'


class DemandMetadataAccessesPerSecondPlugin(GraphBase):
    title = 'Demand Metadata Accesses per Second'
    uses_identifiers = False
    vertical_label = 'accesses/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.dmread'


class DemandDataHitsPerSecondPlugin(GraphBase):
    title = 'Demand Data Hits per Second'
    uses_identifiers = False
    vertical_label = 'hits/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.ddhit'


class DemandDataIOHitsPerSecondPlugin(GraphBase):
    title = 'Demand Data I/O Hits per Second'
    uses_identifiers = False
    vertical_label = 'hits/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.ddioh'


class DemandDataMissesPerSecondPlugin(GraphBase):
    title = 'Demand Data Misses per Second'
    uses_identifiers = False
    vertical_label = 'misses/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.ddmis'


class DemandDataHitPercentagePlugin(GraphBase):
    title = 'Demand Data Hit Percentage'
    uses_identifiers = False
    vertical_label = 'hit%'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.ddh_p'


class DemandDataIOHitPercentagePlugin(GraphBase):
    title = 'Demand Data I/O Hit Percentage'
    uses_identifiers = False
    vertical_label = 'hit%'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.ddi_p'


class DemandDataMissPercentagePlugin(GraphBase):
    title = 'Demand Data Miss Percentage'
    uses_identifiers = False
    vertical_label = 'misses%'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.ddm_p'


class DemandMetadataHitsPerSecondPlugin(GraphBase):
    title = 'Demand Metadata Hits per Second'
    uses_identifiers = False
    vertical_label = 'hits/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.dmhit'


class DemandMetadataIOHitsPerSecondPlugin(GraphBase):
    title = 'Demand Metadata I/O Hits per Second'
    uses_identifiers = False
    vertical_label = 'hits/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.dmioh'


class DemandMetadataMissesPerSecondPlugin(GraphBase):
    title = 'Demand Metadata Misses per Second'
    uses_identifiers = False
    vertical_label = 'misses/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.dmmis'


class DemandMetadataHitPercentagePlugin(GraphBase):
    title = 'Demand Metadata Hit Percentage'
    uses_identifiers = False
    vertical_label = 'hit%'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.dmh_p'


class DemandMetadataIOHitPercentagePlugin(GraphBase):
    title = 'Demand Metadata I/O Hit Percentage'
    uses_identifiers = False
    vertical_label = 'hit%'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.dmi_p'


class DemandMetadataMissPercentagePlugin(GraphBase):
    title = 'Demand Metadata Miss Percentage'
    uses_identifiers = False
    vertical_label = 'misses%'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.dmm_p'


class L2ARCHHitsPerSecondPlugin(GraphBase):
    title = 'L2ARC Hits per Second'
    uses_identifiers = False
    vertical_label = 'hits/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.l2hits'


class L2ARCMissesPerSecondPlugin(GraphBase):
    title = 'L2ARC Misses per Second'
    uses_identifiers = False
    vertical_label = 'misses/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.l2miss'


class TotalL2ARCAccessesPerSecondPlugin(GraphBase):
    title = 'Total L2ARC Accesses per Second'
    uses_identifiers = False
    vertical_label = 'accesses/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.l2read'


class L2ARCHitPercentagePlugin(GraphBase):
    title = 'L2ARC Hit Percentage'
    uses_identifiers = False
    vertical_label = 'hit%'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.l2hit_p'


class L2ARCMissPercentagePlugin(GraphBase):
    title = 'L2ARC Miss Percentage'
    uses_identifiers = False
    vertical_label = 'misses%'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.l2miss_p'


class L2ARCBytesReadPerSecondPlugin(GraphBase):
    title = 'L2ARC Bytes Read per Second'
    uses_identifiers = False
    vertical_label = 'bytes/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.l2bytes'


class L2ARCBytesWrittenPerSecondPlugin(GraphBase):
    title = 'L2ARC Bytes Written per Second'
    uses_identifiers = False
    vertical_label = 'bytes/s'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'truenas_arcstats.l2wbytes'


class DiskTempPlugin(GraphBase):

    title = 'Disks Temperature'
    vertical_label = 'Celsius'
    disk_mapping = {}
    skip_zero_values_in_aggregation = True

    def get_title(self):
        return 'Disk Temperature {identifier}'

    async def build_context(self):
        all_charts = await self.all_charts()
        self.disk_mapping = await self.middleware.run_in_thread(self.get_mapping, all_charts)

    def get_mapping(self, all_charts):
        return {
            get_human_disk_name(disk): disk.identifier for disk in iterate_disks()
            if f'truenas_disk_temp.{disk.identifier}' in all_charts
        }

    async def get_identifiers(self) -> typing.Optional[list]:
        return list(self.disk_mapping.keys())

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return f'truenas_disk_temp.{self.disk_mapping[identifier]}'

    def normalize_metrics(self, metrics) -> dict:
        metrics = super().normalize_metrics(metrics)

        if len(metrics['legend']) < 2:
            for to_add in {'time', 'temperature_value'} - set(metrics['legend']):
                metrics['legend'].append(to_add)
        else:
            metrics['legend'][1] = 'temperature_value'

        return metrics


class UPSBase(GraphBase):

    UPS_IDENTIFIER = None
    skip_zero_values_in_aggregation = True

    async def export_multiple_identifiers(
        self, query_params: dict, identifiers: list, aggregate: bool = True
    ) -> typing.List[dict]:
        self.UPS_IDENTIFIER = f"local_{(await self.middleware.call('ups.config'))['identifier']}"
        return await super().export_multiple_identifiers(query_params, identifiers, aggregate)

    def query_parameters(self) -> dict:
        return super().query_parameters() | {
            'group': 'median'
        }


class UPSChargePlugin(UPSBase):

    title = 'UPS Charging'
    vertical_label = 'Percentage'
    uses_identifiers = False

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return f'upsd_{self.UPS_IDENTIFIER}.battery_charge_percentage'


class UPSRuntimePlugin(UPSBase):

    title = 'UPS Runtime'
    vertical_label = 'Seconds'
    uses_identifiers = False

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return f'upsd_{self.UPS_IDENTIFIER}.battery_estimated_runtime'


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
        return f'upsd_{self.UPS_IDENTIFIER}.{self.IDENTIFIER_MAPPING[identifier]}'


class UPSCurrentPlugin(UPSBase):

    title = 'UPS Input Current'
    vertical_label = 'Ampere'
    uses_identifiers = False

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return f'upsd_{self.UPS_IDENTIFIER}.input_current'


class UPSFrequencyPlugin(UPSBase):

    title = 'UPS Input Frequency'
    vertical_label = 'Hz'
    uses_identifiers = False

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return f'upsd_{self.UPS_IDENTIFIER}.input_frequency'


class UPSLoadPlugin(UPSBase):

    title = 'UPS Input Load'
    vertical_label = 'Percentage'
    uses_identifiers = False

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return f'upsd_{self.UPS_IDENTIFIER}.load_usage'


class UPSTemperaturePlugin(UPSBase):

    title = 'UPS Temperature'
    vertical_label = 'Celsius'
    uses_identifiers = False

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        return f'upsd_{self.UPS_IDENTIFIER}.temperature'
