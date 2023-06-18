import typing

from .graph_base import GraphBase


class CPUPlugin(GraphBase):

    plugin = 'usage'
    title = 'CPU Usage'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.cpu'


class DISKPlugin(GraphBase):

    title = 'Disk I/O Bandwidth'

    async def get_identifiers(self) -> typing.Optional[list]:
        disks = {f'disk.{disk["name"]}' for disk in await self.middleware.call('disk.query')}
        return [disk.rsplit('.')[-1] for disk in (disks & set(await self.all_charts()))]

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return f'disk.{identifier}'


class InterfacePlugin(GraphBase):

    title = 'Interface Traffic'

    async def get_identifiers(self) -> typing.Optional[list]:
        ifaces = {f'net.{i["name"]}' for i in await self.middleware.call('interface.query')}
        return [iface.split('.')[-1] for iface in (ifaces & set(await self.all_charts()))]

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return f'net.{identifier}'


class LoadPlugin(GraphBase):

    title = 'System Load Average'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.load'


class MemoryPlugin(GraphBase):

    title = 'Physical memory utilization'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.ram'


class NFSStatPlugin(GraphBase):

    title = 'NFS input/output stats'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'nfsd.io'


class ProcessesPlugin(GraphBase):

    title = 'System Processes State'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.processes_state'


class SwapPlugin(GraphBase):

    title = 'Swap Utilization'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.swap'


class UptimePlugin(GraphBase):

    title = 'System Uptime'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'system.uptime'


class ZFSArcActualRatePlugin(GraphBase):

    title = 'ZFS Actual Cache Hits Rate'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'zfs.actual_hits_rate'


class ZFSArcRatePlugin(GraphBase):

    title = 'ZFS ARC Hits Rate'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'zfs.hits_rate'


class ZFSArcSizePlugin(GraphBase):

    title = 'ZFS ARC Size'

    def get_chart_name(self, identifier: typing.Optional[str] = None) -> str:
        return 'zfs.arc_size'
