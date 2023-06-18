import re
import statistics
import typing

from .connector import Netdata


GRAPH_PLUGINS = {}
RE_GRAPH_PLUGIN = re.compile(r'^(?P<name>.+)Plugin$')


class GraphMeta(type):

    def __new__(cls, name, bases, dct):
        klass = type.__new__(cls, name, bases, dct)
        reg = RE_GRAPH_PLUGIN.search(name)
        if reg and not hasattr(klass, 'plugin'):
            klass.plugin = reg.group('name').lower()
        elif name != 'GraphBase' and not hasattr(klass, 'plugin'):
            raise ValueError(f'Could not determine plugin name for {name!r}')

        if reg and not hasattr(klass, 'name'):
            klass.name = reg.group('name').lower()
            GRAPH_PLUGINS[klass.name] = klass
        elif hasattr(klass, 'name'):
            GRAPH_PLUGINS[klass.name] = klass
        elif name != 'GraphBase':
            raise ValueError(f'Could not determine class name for {name!r}')
        return klass


class GraphBase(metaclass=GraphMeta):

    aggregations = ('min', 'mean', 'max')
    title = None
    vertical_label = None

    AGG_MAP = {
        'min': min,
        'mean': statistics.mean,
        'max': max,
    }

    def __init__(self, middleware):
        self.middleware = middleware

    def __repr__(self) -> str:
        return f"<Graph: {self.plugin}>"

    async def all_charts(self) -> typing.Dict[str, dict]:
        return await Netdata.get_charts()

    def get_title(self) -> str:
        return self.title

    def get_vertical_label(self) -> str:
        return self.vertical_label

    async def as_dict(self) -> dict:
        return {
            'name': self.name,
            'title': self.title,
            'vertical_label': self.vertical_label,
            'identifiers': await self.get_identifiers(),
        }

    async def get_identifiers(self) -> typing.Optional[list]:
        return None

    def normalize_metrics(self, metrics) -> dict:
        metrics['legend'] = metrics.pop('labels')
        return metrics

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        raise NotImplementedError()

    def query_parameters(self) -> dict:
        return {
            'format': 'json',
            'options': 'flip|nonzero'
        }

    async def export(self, query_params: dict, identifier: typing.Optional[str] = None, aggregate: bool = True):
        data = {
            'name': self.name,
            'identifier': identifier or self.name,
            **self.normalize_metrics(await Netdata.get_chart_metrics(
                self.get_chart_name(identifier), self.query_parameters() | query_params,
            )),
            'start': query_params['after'],
            'end': query_params['before'],
            'aggregations': dict(),
            # TODO: step is missing here and netdata does not seem to have a concept of step
            #  we can get it by dividing total entries by (end - start) but that can have a
            #  performance penalty so leaving this for now
            #  We do get timestamp always as the first column in data so that should suffice
            #  as well i believe for UI team
        }
        if self.aggregations and aggregate:
            # Transpose the data matrix and remove null values
            transposed = [list(
                filter(None.__ne__, i)
            ) for index, i in enumerate(zip(*data['data'])) if index != 0]
            # First column is always timestamp so we remove that
            for agg in self.aggregations:
                if agg in self.AGG_MAP:
                    data['aggregations'][agg] = {
                        k: (self.AGG_MAP[agg](i) if i else None)
                        for k, i in zip(data['legend'][1:], transposed)
                    }
                else:
                    raise RuntimeError(f'Aggregation {agg!r} is invalid.')

        return data
