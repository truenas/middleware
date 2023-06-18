import errno
import time
import typing

from middlewared.schema import accepts, Ref, returns, Str
from middlewared.service import CallError, private, Service, ValidationErrors

from .netdata import GRAPH_PLUGINS
from .netdata.graph_base import GraphBase
from .utils import convert_unit


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

    @accepts(
        Str('name', required=True),
        Ref('reporting_query'),
    )
    @returns()
    async def graphs2(self, name, query):
        """
        Get reporting data for `name` graph.
        """
        graph_plugin = self.__graphs.get(name)
        if graph_plugin is None:
            raise CallError(f'{name!r} is not a valid graph plugin.', errno.ENOENT)

        query_params = await self.middleware.call('reporting.get_query_params', query)
        results = []
        # TODO: Optimize this so when retrieving stats for multiple plugins we do not get all charts
        #  again and again
        for identifier in (await graph_plugin.get_identifiers() or [None]):
            # TODO: Handle 404 gracefully which can happen if no metrics have been collected
            # so far for the identifier/chart in question
            results.append(await graph_plugin.export(query_params, identifier))

        return results

    @private
    def get_query_params(self, query):
        # TODO: For now just average out for aggregate but see what we can do to introduce min/max too
        verrors = ValidationErrors()
        unit = query.get('unit')
        if unit:
            for i in ('start', 'end'):
                if i in query:
                    verrors.add(
                        f'reporting_query.{i}',
                        f'{i!r} should only be used if "unit" attribute is not provided.',
                    )
        else:
            if not query.get('start'):
                verrors.add(
                    'reporting_query.start',
                    'This attribute is required if "unit" attribute is not provided.',
                )

        verrors.check()

        args = {'group': 'average'} if query.get('aggregate') else {}
        end_time = query.get('end') or int(time.time())
        if unit:
            return {'gtime': convert_unit(unit), **args}
        else:
            return {'before': end_time, 'after': query['start'], **args}
