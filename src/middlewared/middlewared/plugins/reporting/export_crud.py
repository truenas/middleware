from __future__ import annotations

import typing

from middlewared.api.base import BaseModel
from middlewared.api.base.jsonschema import get_json_schema
from middlewared.api.current import (
    ReportingExporterSchema,
    ReportingExporterUpdate,
    ReportingExportsCreate,
    ReportingExportsEntry,
)
from middlewared.service import CRUDServicePart, ValidationErrors
import middlewared.sqlalchemy as sa

from .exporters.factory import export_factory

if typing.TYPE_CHECKING:
    from middlewared.service import ServiceContext


class ReportingExportsModel(sa.Model):
    __tablename__ = "reporting_exporters"

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean())
    name = sa.Column(sa.String())
    attributes = sa.Column(sa.JSON(dict))


class ReportingExportsServicePart(CRUDServicePart[ReportingExportsEntry]):
    _datastore = "reporting.exporters"
    _entry = ReportingExportsEntry

    def __init__(self, context: ServiceContext) -> None:
        super().__init__(context)
        self._exporters: dict[str, type[BaseModel]] = {
            k: klass.SCHEMA_MODEL for k, klass in export_factory.get_exporters().items()
        }

    async def do_create(self, data: ReportingExportsCreate) -> ReportingExportsEntry:
        await self.validate(data, "reporting_exporter_create")
        entry = await self._create(data.model_dump())
        if data.enabled:
            # Only restart if this is enabled
            await self._restart_netdata()
        return entry

    async def do_update(self, id_: int, data: ReportingExporterUpdate) -> ReportingExportsEntry:
        old = await self.get_instance(id_)
        new = old.updated(data)
        await self.validate(new, "reporting_exporter_update", old)
        payload = new.model_dump()
        payload.pop("id", None)
        entry = await self._update(id_, payload)
        await self._restart_netdata()
        return entry

    async def do_delete(self, id_: int) -> None:
        await self.get_instance(id_)
        await self._delete(id_)
        await self._restart_netdata()

    def exporter_schemas(self) -> list[ReportingExporterSchema]:
        return [
            ReportingExporterSchema.model_validate({"schema": get_json_schema(model), "key": key})
            for key, model in self._exporters.items()
        ]

    async def validate(
        self,
        data: ReportingExportsEntry,
        schema_name: str,
        old: ReportingExportsEntry | None = None,
    ) -> None:
        verrors = ValidationErrors()
        filters = [["name", "!=", old.name]] if old else []
        filters.append(["name", "=", data.name])
        if await self.query(filters):
            verrors.add(f"{schema_name}.name", "Specified name is already in use")

        exporter_obj = export_factory.exporter(data.attributes.exporter_type)()
        try:
            await exporter_obj.validate_config(data.attributes.model_dump())
        except ValidationErrors as ve:
            verrors.extend(ve)

        verrors.check()

    async def _restart_netdata(self) -> None:
        await (await self.call2(self.s.service.control, "RESTART", "netdata")).wait(raise_error=True)
