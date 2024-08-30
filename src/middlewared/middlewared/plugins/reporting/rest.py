import glob
import logging

from middlewared.service import accepts, Service
from middlewared.schema import Str, Dict, Int
from middlewared.utils.cpu import cpu_info
from middlewared.utils.zfs import query_imported_fast_impl

from .netdata import ClientConnectError, Netdata
from .utils import calculate_disk_space_for_netdata, get_metrics_approximation, TIER_0_POINT_SIZE, TIER_1_POINT_SIZE


logger = logging.getLogger('netdata_api')


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
            logger.debug('Failed to connect to netdata when retrieving all metrics')
            return {}

    def calculated_metrics_count(self):
        return get_metrics_approximation(
            len(self.middleware.call_sync('device.get_disks', False, True)),
            cpu_info()['core_count'],
            self.middleware.call_sync('interface.query', [], {'count': True}),
            len(query_imported_fast_impl()),
            self.middleware.call_sync('datastore.query', 'vm.vm', [], {'count': True}),
            len(glob.glob('/sys/fs/cgroup/**/*.service')),
        )

    def get_disk_space_for_tier0(self):
        config = self.middleware.call_sync('reporting.config')
        return calculate_disk_space_for_netdata(
            self.calculated_metrics_count(), config['tier0_days'], TIER_0_POINT_SIZE, 1,
        )

    def get_disk_space_for_tier1(self):
        config = self.middleware.call_sync('reporting.config')
        return calculate_disk_space_for_netdata(
            self.calculated_metrics_count(), config['tier1_days'], TIER_1_POINT_SIZE, config['tier1_update_interval'],
        )
