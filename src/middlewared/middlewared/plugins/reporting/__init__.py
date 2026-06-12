from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    GraphIdentifier,
    QueryOptions,
    ReportingEntry,
    ReportingGetDataArgs,
    ReportingGetDataResponse,
    ReportingGetDataResult,
    ReportingGraphArgs,
    ReportingGraphResult,
    ReportingGraphsItem,
    ReportingNetdataGetDataArgs,
    ReportingNetdataGetDataResult,
    ReportingNetdataGraphArgs,
    ReportingNetdataGraphResult,
    ReportingNetdataGraphsItem,
    ReportingQuery,
    ReportingUpdate,
    ReportingUpdateArgs,
    ReportingUpdateResult,
)
from middlewared.service import GenericConfigService, filterable_api_method, private

from .config import ReportingConfigServicePart
from .cpu_temps import cpu_temperatures as _cpu_temperatures
from .export import ReportingExportsService
from .graphs import build_graphs, to_entries
from .graphs import graph_names as _graph_names
from .graphs import netdata_get_all as _netdata_get_all
from .graphs import netdata_get_data as _netdata_get_data
from .graphs import netdata_graph as _netdata_graph
from .graphs import netdata_graphs as _netdata_graphs
from .netdata.graph_base import GraphBase
from .netdata_config import netdata_state_location as _netdata_state_location
from .netdata_config import netdata_storage_location as _netdata_storage_location
from .netdata_config import post_dataset_mount_action as _post_dataset_mount_action
from .netdata_config import start_service as _start_service
from .realtime import ReportingRealtimeService

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ('ReportingService',)


class ReportingService(GenericConfigService[ReportingEntry]):

    _svc_part: ReportingConfigServicePart

    class Config:
        cli_namespace = 'system.reporting'
        entry = ReportingEntry
        generic = True
        role_prefix = 'REPORTING'

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self.exporters = ReportingExportsService(middleware)
        self.realtime = ReportingRealtimeService(middleware)
        self._svc_part = ReportingConfigServicePart(self.context)
        self._graphs: dict[str, GraphBase] = build_graphs(middleware)

    @api_method(ReportingUpdateArgs, ReportingUpdateResult, check_annotations=True)
    async def do_update(self, data: ReportingUpdate) -> ReportingEntry:
        """
        `tier1_days` can be set to specify for how many days we want to store reporting history which in netdata
        terms specifies the number of days netdata should be storing data in tier1 storage.
        """
        return await self._svc_part.do_update(data)

    @filterable_api_method(roles=['REPORTING_READ'], item=ReportingGraphsItem, cli_private=True, check_annotations=True)
    async def graphs(
        self, filters: list[typing.Any], options: QueryOptions,
    ) -> list[ReportingGraphsItem] | ReportingGraphsItem | int:
        return to_entries(await _netdata_graphs(self._graphs, filters, options), ReportingGraphsItem)

    @api_method(
        ReportingGetDataArgs, ReportingGetDataResult, roles=['REPORTING_READ'], cli_private=True,
        check_annotations=True,
    )
    async def get_data(self, graphs: list[GraphIdentifier], query: ReportingQuery) -> list[ReportingGetDataResponse]:
        """
        Get reporting data for given graphs.

        List of possible graphs can be retrieved using `reporting.graphs` call.

        For the time period of the graph either `unit` and `page` OR `start` and `end` should be
        used, not both.

        `aggregate` will return aggregate available data for each graph (e.g. min, max, mean).
        """
        return await _netdata_get_data(self.context, self._graphs, graphs, query)

    @api_method(
        ReportingGraphArgs, ReportingGraphResult, roles=['REPORTING_READ'], cli_private=True, check_annotations=True,
    )
    async def graph(self, name: str, query: ReportingQuery) -> list[ReportingGetDataResponse]:
        """
        Get reporting data for `name` graph.
        """
        return await _netdata_graph(self.context, self._graphs, name, query)

    @api_method(
        ReportingNetdataGraphArgs, ReportingNetdataGraphResult, roles=['REPORTING_READ'], cli_private=True,
        check_annotations=True,
    )
    async def netdata_graph(self, name: str, query: ReportingQuery) -> list[ReportingGetDataResponse]:
        """
        Get reporting data for `name` graph.
        """
        return await _netdata_graph(self.context, self._graphs, name, query)

    @filterable_api_method(
        roles=['REPORTING_READ'], item=ReportingNetdataGraphsItem, cli_private=True, check_annotations=True,
    )
    async def netdata_graphs(
        self, filters: list[typing.Any], options: QueryOptions,
    ) -> list[ReportingNetdataGraphsItem] | ReportingNetdataGraphsItem | int:
        """
        Get reporting netdata graphs.
        """
        return to_entries(await _netdata_graphs(self._graphs, filters, options), ReportingNetdataGraphsItem)

    @api_method(
        ReportingNetdataGetDataArgs, ReportingNetdataGetDataResult, roles=['REPORTING_READ'], cli_private=True,
        check_annotations=True,
    )
    async def netdata_get_data(
        self, graphs: list[GraphIdentifier], query: ReportingQuery,
    ) -> list[ReportingGetDataResponse]:
        """
        Get reporting data for given graphs.

        List of possible graphs can be retrieved using `reporting.netdata_graphs` call.
        """
        return await _netdata_get_data(self.context, self._graphs, graphs, query)

    @private
    async def get_all(self, query: dict[str, typing.Any]) -> list[dict[str, typing.Any]]:
        return await _netdata_get_all(self.context, self._graphs, ReportingQuery(**query))

    @private
    async def netdata_get_all(self, query: dict[str, typing.Any]) -> list[dict[str, typing.Any]]:
        return await _netdata_get_all(self.context, self._graphs, ReportingQuery(**query))

    @private
    async def graph_names(self) -> list[str]:
        return _graph_names(self._graphs)

    @private
    async def cpu_temperatures(self) -> dict[str, float]:
        return await _cpu_temperatures(self.context)

    @private
    def netdata_storage_location(self) -> str | None:
        return _netdata_storage_location(self.context)

    @private
    def netdata_state_location(self) -> str:
        return _netdata_state_location()

    @private
    def post_dataset_mount_action(self) -> None:
        _post_dataset_mount_action(self.context)

    @private
    async def start_service(self) -> None:
        await _start_service(self.context)
