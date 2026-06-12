import errno
import typing

from .client import ClientMixin
from .exceptions import ApiException
from .utils import get_query_parameters


class Netdata(ClientMixin):

    @classmethod
    async def get_info(cls) -> dict[str, typing.Any]:
        """Get information about the running netdata instance"""
        return await cls.api_call('info', version='v1')

    @classmethod
    async def get_all_metrics(cls) -> dict[str, typing.Any]:
        return await cls.api_call('allmetrics?format=json', version='v1')

    @classmethod
    async def get_charts(cls) -> dict[str, typing.Any]:
        """
        Get available charts/metrics. Each chart/metric points out information about 1 type of data.
        """
        return typing.cast(dict[str, typing.Any], (await cls.api_call('charts', version='v1'))['charts'])

    @classmethod
    async def get_chart_details(cls, metric: str) -> dict[str, typing.Any]:
        """Get details for `chart`/`metric`"""
        try:
            return typing.cast(dict[str, typing.Any], (await cls.get_charts())[metric])
        except KeyError:
            raise ApiException(f'Metric {metric!r} does not exist', errno=errno.ENOENT)

    @classmethod
    async def get_chart_metrics(
        cls, chart: str, query_params: dict[str, typing.Any] | None = None
    ) -> dict[str, typing.Any]:
        """Get metrics for `chart`"""
        return await cls.api_call(
            f'data?chart={chart}&options=null2zero{get_query_parameters(query_params)}',
            version='v1',
        )

    @classmethod
    async def get_charts_metrics(
        cls, charts: dict[str | None, str], parameters: dict[str, typing.Any]
    ) -> list[tuple[str | None, dict[str, typing.Any]]]:
        """Get metrics for multiple charts"""
        query_params = get_query_parameters(parameters)
        return await cls.api_calls([
            (identifier, f'data?chart={chart_name}&options=null2zero{query_params}')
            for identifier, chart_name in charts.items()
        ])
