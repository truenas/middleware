import copy

import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, returns, Str, Timestamp
from middlewared.service import ConfigService, filterable, filterable_returns, private
from middlewared.validators import Range

from .netdata import GRAPH_PLUGINS


class ReportingModel(sa.Model):
    __tablename__ = 'system_reporting'

    id = sa.Column(sa.Integer(), primary_key=True)
    graphite = sa.Column(sa.String(120), default="")
    graphite_separateinstances = sa.Column(sa.Boolean(), default=False)


class ReportingService(ConfigService):

    class Config:
        datastore = 'system.reporting'
        cli_namespace = 'system.reporting'

    ENTRY = Dict(
        'reporting_entry',
        Str('graphite', required=True),
        Bool('graphite_separateinstances', required=True),
        Int('id', required=True),
    )

    async def do_update(self, data):
        """
        Configure Reporting Database settings.

        `graphite` specifies a destination hostname or IP for collectd data sent by the Graphite plugin..

        `graphite_separateinstances` corresponds to collectd SeparateInstances option.

        .. examples(websocket)::

          Update reporting settings

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "reporting.update",
                "params": [{
                    "graphite": "",
                }]
            }
        """
        old = await self.config()
        new = copy.deepcopy(old)
        new.update(data)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            old['id'],
            new,
            {'prefix': self._config.datastore_prefix}
        )

        return await self.config()

    @filterable
    @filterable_returns(Ref('reporting_graph'))
    async def graphs(self, filters, options):
        return await self.middleware.call('reporting.netdata_graphs', filters, options)

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
        )
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

    @accepts(
        Str('name', required=True),
        Ref('reporting_query'),
    )
    @returns(Ref('netdata_graph_reporting_data'))
    async def graph(self, name, query):
        """
        Get reporting data for `name` graph.
        """
        return await self.middleware.call('reporting.netdata_graph', name, query)
