from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    ReportingExporterSchema,
    ReportingExporterUpdate,
    ReportingExportsCreate,
    ReportingExportsCreateArgs,
    ReportingExportsCreateResult,
    ReportingExportsDeleteArgs,
    ReportingExportsDeleteResult,
    ReportingExportsEntry,
    ReportingExportsExporterSchemasArgs,
    ReportingExportsExporterSchemasResult,
    ReportingExportsUpdateArgs,
    ReportingExportsUpdateResult,
)
from middlewared.service import GenericCRUDService

from .export_crud import ReportingExportsServicePart

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ('ReportingExportsService',)


class ReportingExportsService(GenericCRUDService[ReportingExportsEntry]):

    _svc_part: ReportingExportsServicePart

    class Config:
        namespace = 'reporting.exporters'
        cli_namespace = 'reporting.exporters'
        entry = ReportingExportsEntry
        role_prefix = 'REPORTING'
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = ReportingExportsServicePart(self.context)

    @api_method(ReportingExportsCreateArgs, ReportingExportsCreateResult, check_annotations=True)
    async def do_create(self, data: ReportingExportsCreate) -> ReportingExportsEntry:
        """
        Create a specific reporting exporter configuration containing required details for exporting reporting metrics.
        """
        return await self._svc_part.do_create(data)

    @api_method(ReportingExportsUpdateArgs, ReportingExportsUpdateResult, check_annotations=True)
    async def do_update(self, id_: int, data: ReportingExporterUpdate) -> ReportingExportsEntry:
        """Update Reporting Exporter of ``id``."""
        return await self._svc_part.do_update(id_, data)

    @api_method(ReportingExportsDeleteArgs, ReportingExportsDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> bool:
        """Delete Reporting Exporter of ``id``."""
        await self._svc_part.do_delete(id_)
        return True

    @api_method(
        ReportingExportsExporterSchemasArgs, ReportingExportsExporterSchemasResult, roles=['REPORTING_READ'],
        check_annotations=True,
    )
    def exporter_schemas(self) -> list[ReportingExporterSchema]:
        """
        Get the schemas for all the reporting export types we support with their respective attributes
        required for successfully exporting reporting metrics to them.
        """
        return self._svc_part.exporter_schemas()
