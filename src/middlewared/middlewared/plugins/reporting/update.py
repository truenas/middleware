from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, returns, Str, Timestamp
from middlewared.service import cli_private, filterable, filterable_returns, Service, private
from middlewared.validators import Range

from .netdata import GRAPH_PLUGINS


class ReportingService(Service):

    class Config:
        datastore = 'system.reporting'
        cli_namespace = 'system.reporting'

    @cli_private
    @filterable(roles=['REPORTING_READ'])
    @filterable_returns(Ref('reporting_graph'))
    async def graphs(self, filters, options):
        return await self.middleware.call('reporting.netdata_graphs', filters, options)

    @cli_private
    @accepts(
        List('graphs', items=[
            Dict(
                'graph',
                Str('name', required=True, enum=[i for i in GRAPH_PLUGINS]),
                Str('identifier', default=None, null=True),
            ),
        ], empty=False),
        Dict(
            'reporting_query',
            Str('unit', enum=['HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR']),
            Int('page', default=1, validators=[Range(min_=1)]),
            Timestamp('start'),
            Timestamp('end'),
            Bool('aggregate', default=True),
            register=True,
        ),
        roles=['REPORTING_READ']
    )
    @returns(Ref('netdata_graph_reporting_data'))
    async def get_data(self, graphs, query):
        """
        Get reporting data for given graphs.

        List of possible graphs can be retrieved using `reporting.graphs` call.

        For the time period of the graph either `unit` and `page` OR `start` and `end` should be
        used, not both.

        `aggregate` will return aggregate available data for each graph (e.g. min, max, mean).

        .. examples(websocket)::

          Get graph data of "nfsstat" from the last hour.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "reporting.get_data",
                "params": [
                    [{"name": "nfsstat"}],
                    {"unit": "HOURLY"},
                ]
            }

        """
        return await self.middleware.call('reporting.netdata_get_data', graphs, query)

    @private
    @accepts(Ref('reporting_query'))
    async def get_all(self, query):
        return await self.middleware.call('reporting.netdata_get_all', query)

    @cli_private
    @accepts(
        Str('name', required=True),
        Ref('reporting_query'),
        roles=['REPORTING_READ']
    )
    @returns(Ref('netdata_graph_reporting_data'))
    async def graph(self, name, query):
        """
        Get reporting data for `name` graph.
        """
        return await self.middleware.call('reporting.netdata_graph', name, query)
