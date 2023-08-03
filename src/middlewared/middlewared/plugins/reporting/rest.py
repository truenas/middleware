from middlewared.service import accepts, Service
from middlewared.schema import Str, Dict, Int
from middlewared.utils.cpu import cpu_info

from .netdata import ClientConnectError, Netdata
from .utils import calculate_disk_space_for_netdata, get_metrics_approximation


class NetdataService(Service):

    class Config:
        private = True

    async def get_charts(self):
        return await Netdata.get_charts()

    async def active_total_metrics(self):
        number = 0
        for chart_details in (await Netdata.get_charts()).values():
            number += len(chart_details['dimensions'])
        return number

    @accepts(Str('chart', required=True))
    async def get_chart_details(self, chart):
        return await Netdata.get_chart_details(chart)

    @accepts(
        Str('chart', required=True),
        Dict(
            Int('before', required=False, default=0),
            Int('after', required=False, default=-1),
        ),
    )
    async def get_chart_metrics(self, chart, data):
        return await Netdata.get_chart_metrics(chart, data)

    async def get_all_metrics(self):
        try:
            return await Netdata.get_all_metrics()
        except ClientConnectError:
            self.logger.debug('Failed to connect to netdata when retrieving all metrics', exc_info=True)
            return {}

    def calculated_metrics_count(self):
        return sum(get_metrics_approximation(
            len(self.middleware.call_sync('device.get_disks', False, True)),
            cpu_info()['core_count'],
            self.middleware.call_sync('interface.query', [], {'count': True}),
            self.middleware.call_sync('zfs.pool.query', [], {'count': True}),
        ).values())

    def get_disk_space(self):
        return calculate_disk_space_for_netdata(
            self.calculated_metrics_count(), 7
        )  # We only want to maintain 7 days of stats
