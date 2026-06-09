import errno

from middlewared.service_exception import CallError

from .graphite import GraphiteExporter


class ExportFactory:

    def __init__(self) -> None:
        self._creators: dict[str, type[GraphiteExporter]] = {}

    def register(self, exporter: type[GraphiteExporter]) -> None:
        self._creators[exporter.NAME.upper()] = exporter

    def exporter(self, name: str) -> type[GraphiteExporter]:
        name = name.upper()
        if name not in self._creators:
            raise CallError(f'Unable to locate {name!r} exporter', errno=errno.ENOENT)
        return self._creators[name]

    def get_exporters(self) -> dict[str, type[GraphiteExporter]]:
        return self._creators


export_factory = ExportFactory()
for exporter_type in [
    GraphiteExporter,
]:
    export_factory.register(exporter_type)
