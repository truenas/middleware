from middlewared.api.current import GraphiteExporter as GraphiteExporterModel

from .base import Export


class GraphiteExporter(Export):

    NAME = 'graphite'
    SCHEMA_MODEL = GraphiteExporterModel

    @staticmethod
    async def validate_config(data):
        return data
