import errno

from .client import ClientMixin
from .exceptions import ApiException
from .utils import get_query_parameters


class Netdata(ClientMixin):

    @classmethod
    async def get_info(cls):
        """Get information about the running netdata instance"""
        return await cls.api_call('info', version='v1')

    @classmethod
    async def get_all_metrics(cls):
        return await cls.api_call('allmetrics?format=json', version='v1')

    @classmethod
    async def get_charts(cls):
        """
        Get available charts/metrics. Each chart/metric points out information about 1 type of data.
        """
        return (await cls.api_call('charts', version='v1'))['charts']

    @classmethod
    async def get_chart_details(cls, metric):
        """Get details for `chart`/`metric`"""
        try:
            return (await cls.get_charts())[metric]
        except KeyError:
            raise ApiException(f'Metric {metric!r} does not exist', errno=errno.ENOENT)

    @classmethod
    async def get_chart_metrics(cls, chart, query_params=None):
        """Get metrics for `chart`"""
        return await cls.api_call(
            f'data?chart={chart}{get_query_parameters(query_params)}',
            version='v1',
        )
