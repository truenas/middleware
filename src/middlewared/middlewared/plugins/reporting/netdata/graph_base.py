import re
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

    # TODO: aggregations = ('min', 'mean', 'max')
    title = None
    vertical_label = None
    # TODO: identifier_plugin = True - See if this has any value
    # TODO: rrd_types = None  What to do about this?
    # TODO: rrd_data_extra = None what to do about this?
    # TODO: stacked = False
    # TODO: stacked_show_total = False

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

    def as_dict(self) -> dict:
        return {
            'name': self.name,
            'title': self.title,
            'vertical_label': self.vertical_label,
            'identifiers': self.get_identifiers(),
        }

    async def get_identifiers(self) -> typing.Optional[list]:
        return None

    def normalize_metrics(self, metrics) -> dict:
        return metrics

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        raise NotImplementedError()

    def query_parameters(self) -> dict:
        return {
            'format': 'json',
            'options': 'flip|nonzero'
        }

    async def export(self, query_params: dict, identifier: typing.Optional[str] = None):
        return {
            'name': self.name,
            'identifier': identifier or self.name,
            **self.normalize_metrics(await Netdata.get_chart_metrics(
                self.get_chart_name(identifier), self.query_parameters() | query_params,
            )),
        }
