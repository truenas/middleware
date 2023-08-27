import asyncio
import errno
import time
import typing

from middlewared.schema import accepts, Dict, List, Patch, Ref, returns, Str, Timestamp
from middlewared.service import CallError, filterable, filterable_returns, private, Service, ValidationErrors
from middlewared.utils import filter_list
from middlewared.validators import Range

from .netdata import GRAPH_PLUGINS
from .netdata.graph_base import GraphBase
from .utils import convert_unit, fetch_data_from_graph_plugin


CONCURRENT_TASKS = 400


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

    def _set_page_attr(attr):
        attr.validators = [Range(min_=1)]
        attr.default = 1

    @accepts(
        Str('name', required=True),
        Patch(
            'reporting_query', 'reporting_query_netdata',
            ('edit', {'name': 'page', 'method': _set_page_attr}),
            ('rm', {'name': 'start'}),
            ('rm', {'name': 'end'}),
            ('add', Timestamp('start')),
            ('add', Timestamp('end')),
            register=True,
        ),
    )
    @returns(Ref('netdata_graph_reporting_data'))
    async def netdata_graph(self, name, query):
        """
        Get reporting data for `name` graph.
        """
        graph_plugin = self.__graphs.get(name)
        if graph_plugin is None:
            raise CallError(f'{name!r} is not a valid graph plugin.', errno.ENOENT)

        query_params = await self.middleware.call('reporting.translate_query_params', query)
        identifiers = await graph_plugin.get_identifiers() if graph_plugin.uses_identifiers else [None]

        semaphore = asyncio.Semaphore(CONCURRENT_TASKS)
        graph_plugins = set()
        return [
            result for result in await asyncio.gather(*[fetch_data_from_graph_plugin(
                graph_plugin, query_params, identifier, query['aggregate'], semaphore, graph_plugins,
            ) for identifier in identifiers])
            if result is not None
        ]

    @filterable
    @filterable_returns(Dict(
        'graph',
        Str('name'),
        Str('title'),
        Str('vertical_label'),
        List('identifiers', items=[Str('identifier')], null=True),
    ))
    async def netdata_graphs(self, filters, options):
        """
        Get reporting netdata graphs.
        """
        return filter_list([await i.as_dict() for i in self.__graphs.values()], filters, options)

    @accepts(
        List('graphs', items=[
            Dict(
                'graph',
                Str('name', required=True, enum=[i for i in GRAPH_PLUGINS]),
                Str('identifier', default=None, null=True),
            ),
        ], empty=False),
        Ref('reporting_query_netdata'),
    )
    @returns(List('reporting_data', items=[Dict(
        'netdata_graph_reporting_data',
        Str('name', required=True),
        Str('identifier', required=True, null=True),
        List('data'),
        Dict(
            'aggregations',
            List('min'),
            List('max'),
            List('mean'),
        ),
        additional_attrs=True,
        register=True,
    )]))
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
        graph_plugins = set()
        semaphore = asyncio.Semaphore(CONCURRENT_TASKS)

        return [
            result for result in await asyncio.gather(*[fetch_data_from_graph_plugin(
                self.__graphs[graph['name']], query_params, graph['identifier'], query['aggregate'],
                semaphore, graph_plugins,
            ) for graph in graphs])
            if result is not None
        ]

    @private
    @accepts(Ref('reporting_query'))
    async def netdata_get_all(self, query):
        query_params = await self.middleware.call('reporting.translate_query_params', query)
        rv = []
        for graph_plugin in self.__graphs.values():
            await graph_plugin.build_context()
            for ident in (await graph_plugin.get_identifiers() if graph_plugin.uses_identifiers else [None]):
                rv.append(await graph_plugin.export(query_params, ident, aggregate=query['aggregate']))
        return rv

    @private
    def translate_query_params(self, query):
        unit = query.get('unit')
        if unit:
            verrors = ValidationErrors()
            for i in ('start', 'end'):
                if i in query:
                    verrors.add(
                        f'reporting_query.{i}',
                        f'{i!r} should only be used if "unit" attribute is not provided.',
                    )
            verrors.check()
        else:
            if 'start' not in query:
                unit = 'HOUR'
            else:
                start_time = int(query['start'])

        end_time = int(query.get('end') or time.time())
        return {
            'before': end_time,
            'after': end_time - convert_unit(unit, query['page']) if unit else start_time,
        }
