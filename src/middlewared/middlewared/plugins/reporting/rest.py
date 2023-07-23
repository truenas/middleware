from middlewared.service import accepts, Service
from middlewared.schema import Str, Dict, Int
from middlewared.utils.cpu import cpu_info
from middlewared.utils.disks import get_disks_for_temperature_reading

from .netdata import Netdata
from .utils import calculate_disk_space_for_netdata


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
        return await Netdata.get_all_metrics()

    def get_disk_space(self):
        # TODO: How should we expose graph_age for netdata right now wrt reporting.updte?
        #  Current discussion with Caleb was to store per second data for 7 days
        # FIXME: Fix this based on disks dimensions as just multiplying by 2 is not enough because
        #  more then one dimension of disk is being retrieved by netdata which results in quite a substantial number
        # 415 is an approximation right now based on the number of metrics we have
        metrics = 415 + (2 * len(get_disks_for_temperature_reading())) + cpu_info()['core_count']
        days = self.middleware.call_sync('reporting.config')['graph_age']
        return calculate_disk_space_for_netdata(metrics, days)
