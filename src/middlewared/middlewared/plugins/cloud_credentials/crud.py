from __future__ import annotations

from typing import Any

from middlewared.api.current import (
    CloudCredentialCreate,
    CloudCredentialUpdate,
    CredentialsEntry,
    QueryOptions,
)
from middlewared.service import CallError, CRUDServicePart, ValidationErrors
import middlewared.sqlalchemy as sa


class CloudCredentialModel(sa.Model):
    __tablename__ = "system_cloudcredentials"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(100))
    provider = sa.Column(sa.String(50))
    attributes = sa.Column(sa.JSON(dict, encrypted=True))


class CredentialsServicePart(CRUDServicePart[CredentialsEntry]):
    _datastore = "system.cloudcredentials"
    _entry = CredentialsEntry

    def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        data["provider"] = {"type": data["provider"], **data.pop("attributes")}
        return data

    async def do_create(self, data: CloudCredentialCreate) -> CredentialsEntry:
        await self.validate("cloud_sync_credentials_create", data)
        return await self._create(self._columns(data))

    async def do_update(self, id_: int, data: CloudCredentialUpdate) -> CredentialsEntry:
        new = (await self.get_instance(id_)).updated(data)
        await self.validate("cloud_sync_credentials_update", new, id_)
        return await self._update(id_, self._columns(new))

    async def do_delete(self, id_: int) -> bool:
        cloudsync_tasks = await self.call2(
            self.s.cloudsync.query,
            [["credentials.id", "=", id_]],
            QueryOptions(select=["id", "credentials", "description"]),
        )
        if cloudsync_tasks:
            raise CallError(
                f"This credential is used by cloud sync task {cloudsync_tasks[0].description or cloudsync_tasks[0].id}"
            )

        cloud_backup_tasks = await self.call2(
            self.s.cloud_backup.query,
            [["credentials.id", "=", id_]],
            QueryOptions(select=["id", "credentials", "description"]),
        )
        if cloud_backup_tasks:
            raise CallError(
                "This credential is used by cloud backup task "
                f"{cloud_backup_tasks[0].description or cloud_backup_tasks[0].id}"
            )

        return await self.middleware.call(  # type: ignore[no-any-return]
            "datastore.delete",
            "system.cloudcredentials",
            id_,
        )

    async def validate(self, schema_name: str, credential: CredentialsEntry, id_: int | None = None) -> None:
        verrors = ValidationErrors()
        await self._ensure_unique(verrors, schema_name, "name", credential.name, id_)
        verrors.check()

    def _columns(self, credential: CredentialsEntry | CloudCredentialCreate) -> dict[str, Any]:
        provider = credential.provider.model_dump(expose_secrets=True)
        return {
            "name": credential.name,
            "provider": provider.pop("type"),
            "attributes": provider,
        }
