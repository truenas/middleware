from middlewared.schema import accepts, Bool, Dict, Int, Str
from middlewared.validators import Port, Range

from .base import Export


class GraphiteExporter(Export):

    NAME = 'graphite'
    SCHEMA = Dict(
        'graphite',
        Str('destination_ip', required=True),
        Int('destination_port', required=True, validators=[Port()]),
        Str('prefix', default='dragonfish'),
        Str('hostname', default='truenas'),
        Int('update_every', validators=[Range(min_=1)], default=1),
        Int('buffer_on_failures', validators=[Range(min_=1)], default=10),
        Bool('send_names_instead_of_ids', default=True),
        Str('matching_charts', default='*'),
    )

    @staticmethod
    @accepts(SCHEMA)
    async def validate_config(data):
        return data
