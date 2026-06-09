import typing

from middlewared.api.base import BaseModel
from middlewared.api.current import GraphiteExporter as GraphiteExporterModel


class GraphiteExporter:

    NAME: typing.ClassVar[str] = 'graphite'
    SCHEMA_MODEL: typing.ClassVar[type[BaseModel]] = GraphiteExporterModel

    @staticmethod
    async def validate_config(data: typing.Any) -> typing.Any:
        return data
