from middlewared.api.current import GraphiteExporter as GraphiteExporterModel


class GraphiteExporter:

    NAME = "graphite"
    SCHEMA_MODEL = GraphiteExporterModel

    @staticmethod
    async def validate_config(data):
        return data
