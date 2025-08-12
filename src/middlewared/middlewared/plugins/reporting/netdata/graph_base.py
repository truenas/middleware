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
        elif not name.endswith('Base') and not hasattr(klass, 'plugin'):
            raise ValueError(f'Could not determine plugin name for {name!r}')

        if reg and not hasattr(klass, 'name'):
            klass.name = reg.group('name').lower()
            GRAPH_PLUGINS[klass.name] = klass
        elif hasattr(klass, 'name'):
            GRAPH_PLUGINS[klass.name] = klass
        elif not name.endswith('Base'):
            raise ValueError(f'Could not determine class name for {name!r}')
        return klass


class GraphBase(metaclass=GraphMeta):

    aggregations = ('min', 'mean', 'max')
    title = None
    uses_identifiers = True
    vertical_label = None
    skip_zero_values_in_aggregation = False

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
        try:
            return await Netdata.get_charts()
        except Exception as e:
            self.middleware.logger.warning('Failed to connect to netdata: %s', e)
            return {}

    def get_title(self) -> str:
        return self.title

    def get_vertical_label(self) -> str:
        return self.vertical_label

    async def build_context(self):
        pass

    async def as_dict(self) -> dict:
        await self.build_context()
        return {
            'name': self.name,
            'title': self.get_title(),
            'vertical_label': self.vertical_label,
            'identifiers': await self.get_identifiers() if self.uses_identifiers else None,
        }

    async def get_identifiers(self) -> list:
        return []

    def normalize_metrics(self, metrics) -> dict:
        metrics['legend'] = metrics.pop('labels')
        if metrics['data'] and metrics['data'][-1] and all(m == 0 for m in metrics['data'][-1][1:]):
            # we will now remove last entry of data as when end if sometimes is specified as time which does not
            # exist in netdata database, netdata adds a last entry of 0 which we don't want to show
            metrics['data'].pop()
        return metrics

    def get_chart_name(self, identifier: typing.Optional[str]) -> str:
        raise NotImplementedError()

    def aggregate_metrics(self, data):
        # Initialize the aggregation dictionary
        aggregations = {}
        all_aggregation_values = {
            'min': float('inf'),
            'max': float('-inf'),
            'mean': 0.0,
            'total_points': 0
        }
        default_aggregation_values = {
            key: all_aggregation_values[key] for key in set(self.aggregations) | {'total_points'}
        }
        final_aggregated_values = {k: {} for k in self.aggregations}
        for legend in data['legend'][1:]:
            aggregations[legend] = default_aggregation_values.copy()

        # Traverse the data matrix and calculate aggregations
        data_length = len(data['data'])
        for index, row in enumerate(data['data']):
            for idx, legend in enumerate(data['legend'][1:], start=1):
                value = row[idx]

                # Skip None values
                if value is None or (self.skip_zero_values_in_aggregation and value == 0):
                    continue

                # Update the aggregation values
                # When using built in min/max functions, a lag of 5 secs was seen when doing this math for
                # 1200 disks, so we are doing it manually here with if/else clauses
                if 'min' in final_aggregated_values and aggregations[legend]['min'] > value:
                    aggregations[legend]['min'] = value
                if 'max' in final_aggregated_values and aggregations[legend]['max'] < value:
                    aggregations[legend]['max'] = value
                if 'mean' in final_aggregated_values:
                    aggregations[legend]['mean'] += value

                aggregations[legend]['total_points'] += 1

                # Reason for doing this here is to avoid another loop because with 1200 disks adding another loop
                # even just for legends is an expensive operation
                if index == data_length - 1:
                    # Calculate the final mean for each metric
                    if 'max' in final_aggregated_values:
                        final_aggregated_values['max'][legend] = aggregations[legend]['max']
                    if 'min' in final_aggregated_values:
                        final_aggregated_values['min'][legend] = aggregations[legend]['min']
                    if 'mean' in final_aggregated_values:
                        if aggregations[legend]['total_points'] > 0:
                            aggregations[legend]['mean'] /= aggregations[legend]['total_points']
                        else:
                            aggregations[legend]['mean'] = 0.0

                        final_aggregated_values['mean'][legend] = aggregations[legend]['mean']

        data['aggregations'] = final_aggregated_values
        return data

    def query_parameters(self) -> dict:
        return {
            'format': 'json',
            'options': 'flip|null2zero|natural-points',
            'points': 2999,  # max supported points are 3000 in UI, we keep 2999 because netdata accounts for index 0
            'group': 'average',
            'gtime': 0,
        }

    def process_chart_metrics(self, responses: list, query_params: dict, aggregate: bool) -> list:
        results = []
        for identifier, chart_metrics in responses:
            data = {
                'name': self.name,
                'identifier': identifier or self.name,
                **self.normalize_metrics(chart_metrics),
                'start': query_params['after'],
                'end': query_params['before'],
                'aggregations': dict(),
            }
            if self.aggregations and aggregate:
                data = self.aggregate_metrics(data)
            else:
                data['aggregations'] = None

            results.append(data)

        return results

    async def export_multiple_identifiers(
        self, query_params: dict, identifiers: list, aggregate: bool = True
    ) -> typing.List[dict]:
        responses = await Netdata.get_charts_metrics({
            identifier: self.get_chart_name(identifier) for identifier in identifiers
        }, self.query_parameters() | query_params)

        # Normalize the results
        return await self.middleware.run_in_thread(self.process_chart_metrics, responses, query_params, aggregate)
