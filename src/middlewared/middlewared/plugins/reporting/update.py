import copy
import errno

import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Bool, Dict, Int, List, Patch, Ref, returns, Str
from middlewared.service import CallError, ConfigService, filterable, filterable_returns, private, ValidationErrors
from middlewared.utils import filter_list, osc, run
from middlewared.validators import Range

from .rrd_utils import RRD_PLUGINS


class ReportingModel(sa.Model):
    __tablename__ = 'system_reporting'

    id = sa.Column(sa.Integer(), primary_key=True)
    cpu_in_percentage = sa.Column(sa.Boolean(), default=False)
    graphite = sa.Column(sa.String(120), default="")
    graph_age = sa.Column(sa.Integer(), default=12)
    graph_points = sa.Column(sa.Integer(), default=1200)
    graphite_separateinstances = sa.Column(sa.Boolean(), default=False)


class ReportingService(ConfigService):

    class Config:
        datastore = 'system.reporting'
        cli_namespace = 'system.reporting'

    ENTRY = Dict(
        'reporting_entry',
        Bool('cpu_in_percentage', required=True),
        Str('graphite', required=True),
        Bool('graphite_separateinstances', required=True),
        Int('graph_age', validators=[Range(min=1, max=60)], required=True),
        Int('graph_points', validators=[Range(min=1, max=4096)], required=True),
        Int('id', required=True),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__rrds = {}
        for name, klass in RRD_PLUGINS.items():
            self.__rrds[name] = klass(self.middleware)

    @accepts(
        Patch(
            'reporting_entry', 'reporting_update',
            ('add', Bool('confirm_rrd_destroy')),
            ('rm', {'name': 'id'}),
            ('attr', {'update': True}),
        ),
    )
    async def do_update(self, data):
        """
        Configure Reporting Database settings.

        If `cpu_in_percentage` is `true`, collectd reports CPU usage in percentage instead of "jiffies".

        `graphite` specifies a destination hostname or IP for collectd data sent by the Graphite plugin..

        `graphite_separateinstances` corresponds to collectd SeparateInstances option.

        `graph_age` specifies the maximum age of stored graphs in months. `graph_points` is the number of points for
        each hourly, daily, weekly, etc. graph. Changing these requires destroying the current reporting database,
        so when these fields are changed, an additional `confirm_rrd_destroy: true` flag must be present.

        .. examples(websocket)::

          Update reporting settings

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "reporting.update",
                "params": [{
                    "cpu_in_percentage": false,
                    "graphite": "",
                }]
            }

          Recreate reporting database with new settings

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "reporting.update",
                "params": [{
                    "graph_age": 12,
                    "graph_points": 1200,
                    "confirm_rrd_destroy": true,
                }]
            }
        """

        confirm_rrd_destroy = data.pop('confirm_rrd_destroy', False)

        old = await self.config()

        new = copy.deepcopy(old)
        new.update(data)

        verrors = ValidationErrors()

        destroy_database = False
        for k in ['graph_age', 'graph_points']:
            if old[k] != new[k]:
                destroy_database = True

                if not confirm_rrd_destroy:
                    verrors.add(
                        f'reporting_update.{k}',
                        'Changing this option requires destroying the reporting database. This action '
                        'must be confirmed by setting confirm_rrd_destroy flag',
                    )

        if verrors:
            raise verrors

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            old['id'],
            new,
            {'prefix': self._config.datastore_prefix}
        )

        if destroy_database:
            await self.middleware.call('service.stop', 'collectd')
            await self.middleware.call('service.stop', 'rrdcached')
            await run(
                'sh', '-c', f'rm {"--one-file-system -rf" if osc.IS_LINUX else "-rfx"} /var/db/collectd/rrd/*',
                check=False
            )
            await self.middleware.call('reporting.setup')
            await self.middleware.call('service.start', 'rrdcached')

        await self.middleware.call('service.restart', 'collectd')

        return await self.config()

    @filterable
    @filterable_returns(Dict(
        'graph',
        Str('name'),
        Str('title'),
        Str('vertical_label'),
        List('identifiers', items=[Str('identifier')], null=True),
        Bool('stacked'),
        Bool('stacked_show_total'),
    ))
    def graphs(self, filters, options):
        return filter_list([
            i.__getstate__() for i in self.__rrds.values() if i.has_data()
        ], filters, options)

    def __rquery_to_start_end(self, query):
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
                unit = 'HOURLY'
            else:
                starttime = query['start']
                endtime = query.get('end') or 'now'

        if unit:
            unit = unit[0].lower()
            page = query['page']
            starttime = f'end-{page + 1}{unit}'
            if not page:
                endtime = 'now'
            else:
                endtime = f'now-{page}{unit}'
        return starttime, endtime

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
            Int('page', default=0),
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
    def get_data(self, graphs, query):
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
        starttime, endtime = self.__rquery_to_start_end(query)
        rv = []
        for i in graphs:
            try:
                rrd = self.__rrds[i['name']]
            except KeyError:
                raise CallError(f'Graph {i["name"]!r} not found.', errno.ENOENT)
            rv.append(
                rrd.export(i['identifier'], starttime, endtime, aggregate=query['aggregate'])
            )
        return rv

    @private
    @accepts(Ref('reporting_query'))
    def get_all(self, query):
        starttime, endtime = self.__rquery_to_start_end(query)
        rv = []
        for rrd in self.__rrds.values():
            idents = rrd.get_identifiers()
            if idents is None:
                idents = [None]
            for ident in idents:
                rv.append(rrd.export(ident, starttime, endtime, aggregate=query['aggregate']))
        return rv
