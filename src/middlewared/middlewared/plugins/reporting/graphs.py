import collections
import errno
import time
import typing

from middlewared.api import api_method
from middlewared.api.current import (
    ReportingNetdataGraphArgs, ReportingNetdataGraphResult, ReportingNetdataGraphsItem, ReportingNetdataGetDataArgs,
    ReportingNetdataGetDataResult,
)
from middlewared.service import CallError, filterable_api_method, private, Service, ValidationErrors
from middlewared.utils import filter_list

from .netdata import GRAPH_PLUGINS
from .netdata.graph_base import GraphBase
from .utils import convert_unit, fetch_data_from_graph_plugins


class ReportingService(Service):

    class Config:
        cli_namespace = 'system.reporting'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__graphs: typing.Dict[str, GraphBase] = {}
        for name, klass in GRAPH_PLUGINS.items():
            self.__graphs[name] = klass(self.middleware)

    @private
    async def graph_names(self):
        return list(self.__graphs.keys())

    @api_method(ReportingNetdataGraphArgs, ReportingNetdataGraphResult, roles=['REPORTING_READ'], cli_private=True)
    async def netdata_graph(self, name, query):
        """
        Get reporting data for `name` graph.
        """
        graph_plugin = self.__graphs.get(name)
        if graph_plugin is None:
            raise CallError(f'{name!r} is not a valid graph plugin.', errno.ENOENT)

        query_params = await self.middleware.call('reporting.translate_query_params', query)
        await graph_plugin.build_context()
        identifiers = await graph_plugin.get_identifiers() if graph_plugin.uses_identifiers else [None]

        return await graph_plugin.export_multiple_identifiers(query_params, identifiers, query['aggregate'])

    @filterable_api_method(roles=['REPORTING_READ'], item=ReportingNetdataGraphsItem, cli_private=True)
    async def netdata_graphs(self, filters, options):
        """
        Get reporting netdata graphs.
        """
        return filter_list([await i.as_dict() for i in self.__graphs.values()], filters, options)

    @api_method(ReportingNetdataGetDataArgs, ReportingNetdataGetDataResult, roles=['REPORTING_READ'], cli_private=True)
    async def netdata_get_data(self, graphs, query):
        """
        Get reporting data for given graphs.

        List of possible graphs can be retrieved using `reporting.netdata_graphs` call.

        For the time period of the graph either `unit` and `page` OR `start` and `end` should be
        used, not both.

        `aggregate` will return aggregate available data for each graph (e.g. min, max, mean).

        .. examples(websocket)::

          Get graph data of "nfsstat" from the last hour.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "reporting.netdata_get_data",
                "params": [
                    [{"name": "cpu"}],
                    {"unit": "HOURLY"},
                ]
            }

        """
        query_params = await self.middleware.call('reporting.translate_query_params', query)
        graph_plugins = collections.defaultdict(list)
        for graph in graphs:
            graph_plugins[self.__graphs[graph['name']]].append(graph['identifier'])

        results = []
        async for result in fetch_data_from_graph_plugins(graph_plugins, query_params, query['aggregate']):
            results.extend(result)

        return results

    @private
    async def netdata_get_all(self, query):
        query_params = await self.middleware.call('reporting.translate_query_params', query)
        rv = []
        for graph_plugin in self.__graphs.values():
            await graph_plugin.build_context()
            identifiers = await graph_plugin.get_identifiers() if graph_plugin.uses_identifiers else [None]
            rv.extend(await graph_plugin.export_multiple_identifiers(query_params, identifiers, query['aggregate']))
        return rv

    @private
    def translate_query_params(self, query):
        # TODO: Add unit tests for this please
        unit = query.get('unit')
        if unit:
            verrors = ValidationErrors()
            for i in ('start', 'end'):
                if query.get(i) is not None:
                    verrors.add(
                        f'reporting_query.{i}',
                        f'{i!r} should only be used if "unit" attribute is not provided.',
                    )
            verrors.check()
        else:
            if query.get('start') is None:
                unit = 'HOUR'
            else:
                start_time = int(query['start'])

        end_time = int(query.get('end') or time.time())
        return {
            'before': end_time,
            'after': end_time - convert_unit(unit, query['page']) if unit else start_time,
        }
