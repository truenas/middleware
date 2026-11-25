from __future__ import annotations

from typing import Any

from middlewared.api.current import (
    SharingWebshareCreate,
    SharingWebshareEntry,
    SharingWebshareOptions,
    SharingWebshareUpdate,
)
from middlewared.service import SharingServicePart, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.types import AuditCallback

from .sharing_validate import validate_webshare
from .utils import reload_webshare


class SharingWebshareModel(sa.Model):
    __tablename__ = "sharing_webshare_share"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255))
    path = sa.Column(sa.String(255))
    dataset = sa.Column(sa.String(255), nullable=True)
    relative_path = sa.Column(sa.String(255), nullable=True)
    is_home_base = sa.Column(sa.Boolean())
    enabled = sa.Column(sa.Boolean())
    readonly = sa.Column(sa.Boolean())


class SharingWebsharePart(SharingServicePart[SharingWebshareEntry]):
    _datastore = "sharing.webshare_share"
    _datastore_sql_filters = frozenset(
        (
            "id",
            "name",
            "path",
            "dataset",
            "relative_path",
            "is_home_base",
            "enabled",
            "readonly",
        )
    )
    _entry = SharingWebshareEntry

    include_tier_info = True
    readonly_field = "readonly"

    async def do_create(
        self, data: SharingWebshareCreate, options: SharingWebshareOptions = SharingWebshareOptions()
    ) -> SharingWebshareEntry:
        entry = await self._create(await self._validated_row("sharing_webshare_create", data, options))

        await reload_webshare(self)

        return entry

    async def do_update(
        self,
        audit_callback: AuditCallback,
        id_: int,
        data: SharingWebshareUpdate,
        options: SharingWebshareOptions = SharingWebshareOptions(),
    ) -> SharingWebshareEntry:
        old = await self.get_instance(id_)
        audit_callback(old.name)

        new = old.updated(data)
        entry = await self._update(id_, await self._validated_row("sharing_webshare_update", new, options, old))

        await reload_webshare(self)

        return entry

    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> None:
        share = await self.get_instance(id_)
        audit_callback(share.name)

        await self._delete(id_)

        await reload_webshare(self)

    def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        for computed in ("id", self.locked_field, "tier"):
            data.pop(computed, None)
        return data

    async def _validated_row(
        self,
        schema_name: str,
        data: SharingWebshareEntry,
        options: SharingWebshareOptions,
        old: SharingWebshareEntry | None = None,
    ) -> dict[str, Any]:
        verrors = ValidationErrors()
        path = await validate_webshare(self, data, schema_name, verrors, old)
        if data.enabled and not options.force_path_conflicts:
            await self.call2(self.s.filesystem.compatibility.validate_path, verrors, data.path, "sharing.webshare")
        verrors.check()

        return {**data.model_dump(), **path}
