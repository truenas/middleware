from __future__ import annotations

import glob
import logging
import typing

from pydantic import Field

from middlewared.api import api_method
from middlewared.api.base import BaseModel, NonEmptyString
from middlewared.service import Service
from middlewared.utils.cpu import cpu_info
from middlewared.utils.disk_stats import get_disk_stats
from middlewared.utils.zfs import query_imported_fast_impl

from .netdata import ClientConnectError, Netdata
from .utils import TIER_0_POINT_SIZE, TIER_1_POINT_SIZE, calculate_disk_space_for_netdata, get_metrics_approximation

logger = logging.getLogger('netdata_api')


class ChartMetricsDataArgs(BaseModel):
    before: int = 0
    after: int = -1


class ChartMetricsArgs(BaseModel):
    chart: NonEmptyString
    data: ChartMetricsDataArgs = Field(default_factory=lambda: ChartMetricsDataArgs())


class ChartMetricsResult(BaseModel):
    result: dict[str, typing.Any]


class ChartDetailsArgs(BaseModel):
    chart: NonEmptyString


class ChartDetailsResult(BaseModel):
    result: dict[str, typing.Any]


class NetdataService(Service):

    class Config:
        private = True

    async def get_charts(self) -> dict[str, typing.Any]:
        return await Netdata.get_charts()

    async def active_total_metrics(self) -> int:
        number = 0
        for chart_details in (await Netdata.get_charts()).values():
            number += len(chart_details['dimensions'])
        return number

    @api_method(ChartDetailsArgs, ChartDetailsResult, private=True, check_annotations=True)
    async def get_chart_details(self, chart: str) -> dict[str, typing.Any]:
        return await Netdata.get_chart_details(chart)

    @api_method(ChartMetricsArgs, ChartMetricsResult, private=True, check_annotations=True)
    async def get_chart_metrics(self, chart: str, data: ChartMetricsDataArgs) -> dict[str, typing.Any]:
        return await Netdata.get_chart_metrics(chart, data.model_dump())

    async def get_all_metrics(self) -> dict[str, typing.Any]:
        try:
            return await Netdata.get_all_metrics()
        except ClientConnectError:
            logger.debug('Failed to connect to netdata when retrieving all metrics')
            return {}

    def calculated_metrics_count(self) -> dict[int, int]:
        return get_metrics_approximation(
            len(self.middleware.call_sync('device.get_disks', False, True)),
            cpu_info()['core_count'] or 0,
            self.middleware.call_sync('interface.query', [], {'count': True}),
            len(query_imported_fast_impl()),
            self.middleware.call_sync('datastore.query', 'vm.vm', [], {'count': True}),
            len(glob.glob('/sys/fs/cgroup/**/*.service')),
        )

    def get_disk_space_for_tier0(self) -> int:
        config = self.call_sync2(self.s.reporting.config)
        return calculate_disk_space_for_netdata(
            self.calculated_metrics_count(), config.tier0_days, TIER_0_POINT_SIZE, 1,
        )

    def get_disk_space_for_tier1(self) -> int:
        config = self.call_sync2(self.s.reporting.config)
        return calculate_disk_space_for_netdata(
            self.calculated_metrics_count(), config.tier1_days, TIER_1_POINT_SIZE, config.tier1_update_interval,
        )

    def get_disk_stats(self) -> dict[str, typing.Any]:
        return get_disk_stats()
