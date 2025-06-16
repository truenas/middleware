import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    ReportingEntry, ReportingGraphsItem, ReportingUpdateArgs, ReportingUpdateResult, ReportingGetDataArgs,
    ReportingGetDataResult, ReportingGraphResult, ReportingGraphArgs,
)
from middlewared.service import filterable_api_method, ConfigService, private


class ReportingModel(sa.Model):
    __tablename__ = 'reporting'

    id = sa.Column(sa.Integer(), primary_key=True)
    tier0_days = sa.Column(sa.Integer(), default=7)
    tier1_days = sa.Column(sa.Integer(), default=30)
    tier1_update_interval = sa.Column(sa.Integer(), default=300)  # This is in seconds


class ReportingService(ConfigService):

    class Config:
        cli_namespace = 'system.reporting'
        datastore = 'reporting'
        role_prefix = 'REPORTING'
        entry = ReportingEntry

    @api_method(ReportingUpdateArgs, ReportingUpdateResult)
    async def do_update(self, data):
        """
        `tier1_days` can be set to specify for how many days we want to store reporting history which in netdata
        terms specifies the number of days netdata should be storing data in tier1 storage.
        """
        old_config = await self.config()
        config = old_config.copy()
        config.update(data)

        await self.middleware.call('datastore.update', self._config.datastore, old_config['id'], config)

        await (await self.middleware.call('service.control', 'RESTART', 'netdata')).wait(raise_error=True)
        return await self.config()

    @filterable_api_method(roles=['REPORTING_READ'], item=ReportingGraphsItem, cli_private=True)
    async def graphs(self, filters, options):
        return await self.middleware.call('reporting.netdata_graphs', filters, options)

    @api_method(ReportingGetDataArgs, ReportingGetDataResult, roles=['REPORTING_READ'], cli_private=True)
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
    async def get_all(self, query):
        return await self.middleware.call('reporting.netdata_get_all', query)

    @api_method(ReportingGraphArgs, ReportingGraphResult, roles=['REPORTING_READ'], cli_private=True)
    async def graph(self, name, query):
        """
        Get reporting data for `name` graph.
        """
        return await self.middleware.call('reporting.netdata_graph', name, query)
