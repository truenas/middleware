from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, returns, Str
from middlewared.service import cli_private, filterable, filterable_returns, private, Service
from middlewared.validators import Range


class ReportingService(Service):

    class Config:
        cli_namespace = 'system.reporting'

    @accepts(Bool('start_collectd', default=True, hidden=True))
    @returns()
    async def clear(self, start_collectd):
        """
        Clear reporting database.
        """

    @cli_private
    @filterable
    @filterable_returns(Dict(
        'graph',
        Str('name'),
        Str('title'),
        Str('vertical_label'),
        List('identifiers', items=[Str('identifier')], null=True),
    ))
    async def graphs(self, filters, options):
        return await self.middleware.call('reporting.netdata_graphs', filters, options)

    @cli_private
    @accepts(
        List('graphs', items=[
            Dict(
                'graph',
                Str('name', required=True),
                Str('identifier', default=None, null=True),
            ),
        ], empty=False),
        Dict(
            'reporting_query',
            Str('unit', enum=['HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR']),
            Int('page', default=1, validators=[Range(min=1)]),
            Str('start', empty=False),
            Str('end', empty=False),
            Bool('aggregate', default=True),
            register=True,
        )
    )
    @returns(List('reporting_data', items=[Dict(
        'graph_reporting_data',
        Str('name', required=True),
        Str('identifier', required=True, null=True),
        List('data'),
        Dict(
            'aggregations',
            List('min'),
            List('max'),
            List('mean'),
        ),
        additional_attrs=True
    )]))
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
