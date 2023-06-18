from middlewared.service import accepts, Service
from middlewared.schema import Str, Dict, Int

from .netdata import Netdata


class ReportingRestService(Service):

    class Config:
        private = True
        namespace = 'reporting.rest'

    async def get_charts(self):
        return await Netdata.get_charts()

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
