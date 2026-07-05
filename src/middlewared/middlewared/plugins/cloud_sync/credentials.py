from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any

from middlewared.api import api_method
from middlewared.api.current import (
    CloudCredentialCreate,
    CloudCredentialProvider,
    CloudCredentialUpdate,
    CredentialsCreateArgs,
    CredentialsCreateResult,
    CredentialsDeleteArgs,
    CredentialsDeleteResult,
    CredentialsEntry,
    CredentialsS3ProviderChoicesArgs,
    CredentialsS3ProviderChoicesResult,
    CredentialsUpdateArgs,
    CredentialsUpdateResult,
    CredentialsVerifyArgs,
    CredentialsVerifyResult,
)
from middlewared.rclone.remote.s3_providers import S3_PROVIDERS
from middlewared.service import CallError, CRUDServicePart, GenericCRUDService, ValidationErrors
import middlewared.sqlalchemy as sa

from .rclone import RcloneConfig, RcloneConfigParams, lsjson_error_excerpt

if TYPE_CHECKING:
    from middlewared.main import Middleware


class CloudCredentialModel(sa.Model):
    __tablename__ = 'system_cloudcredentials'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(100))
    provider = sa.Column(sa.String(50))
    attributes = sa.Column(sa.JSON(dict, encrypted=True))


def extend_credential(data: dict[str, Any]) -> dict[str, Any]:
    """Expand a stored ``system.cloudcredentials`` row into the ``{provider: {type, ...}}`` shape."""
    data["provider"] = {
        "type": data["provider"],
        **data.pop("attributes"),
    }
    return data


class CredentialsServicePart(CRUDServicePart[CredentialsEntry]):
    _datastore = "system.cloudcredentials"
    _entry = CredentialsEntry

    def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return extend_credential(data)

    def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        data["attributes"] = data["provider"]
        data["provider"] = data["attributes"].pop("type")
        return data

    async def do_create(self, data: CloudCredentialCreate) -> CredentialsEntry:
        verrors = ValidationErrors()
        await self._ensure_unique(verrors, "cloud_sync_credentials_create", "name", data.name)
        verrors.check()

        return await self._create(data.model_dump(by_alias=True, context={"expose_secrets": True}))

    async def do_update(self, id_: int, data: CloudCredentialUpdate) -> CredentialsEntry:
        old = await self.get_instance(id_)
        new = old.updated(data)

        verrors = ValidationErrors()
        await self._ensure_unique(verrors, "cloud_sync_credentials_update", "name", new.name, id_)
        verrors.check()

        return await self._update(id_, new.model_dump(by_alias=True, context={"expose_secrets": True}))

    async def do_delete(self, id_: int) -> None:
        sync_tasks = await self.call2(self.s.cloudsync.query, [["credentials.id", "=", id_]])
        if sync_tasks:
            raise CallError(
                f"This credential is used by cloud sync task {sync_tasks[0].description or sync_tasks[0].id}"
            )

        backup_tasks = await self.call2(self.s.cloud_backup.query, [["credentials.id", "=", id_]])
        if backup_tasks:
            raise CallError(
                f"This credential is used by cloud backup task {backup_tasks[0].description or backup_tasks[0].id}"
            )

        await self._delete(id_)

    def verify(self, provider: CloudCredentialProvider) -> dict[str, Any]:
        self.middleware.call_sync("network.general.will_perform_activity", "cloud_sync")

        credentials = CredentialsEntry(id=0, name="verify", provider=provider)
        with RcloneConfig(RcloneConfigParams(credentials=credentials)) as config:
            proc = subprocess.run(
                ["rclone", "--config", config.config_path, "--contimeout", "15s", "--timeout", "30s", "lsjson",
                 "remote:"],
                check=False,
                encoding="utf8",
                capture_output=True,
            )
            if proc.returncode == 0:
                return {"valid": True}
            else:
                return {"valid": False, "error": proc.stderr, "excerpt": lsjson_error_excerpt(proc.stderr)}


class CredentialsService(GenericCRUDService[CredentialsEntry]):
    _svc_part: CredentialsServicePart

    class Config:
        namespace = "cloudsync.credentials"
        cli_namespace = "task.cloud_sync.credential"
        entry = CredentialsEntry
        generic = True
        role_prefix = "CLOUD_SYNC"

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = CredentialsServicePart(self.context)

    @api_method(CredentialsCreateArgs, CredentialsCreateResult, check_annotations=True)
    async def do_create(self, data: CloudCredentialCreate) -> CredentialsEntry:
        """Create Cloud Sync Credentials."""
        return await self._svc_part.do_create(data)

    @api_method(CredentialsUpdateArgs, CredentialsUpdateResult, check_annotations=True)
    async def do_update(self, id_: int, data: CloudCredentialUpdate) -> CredentialsEntry:
        """Update Cloud Sync Credentials of ``id``."""
        return await self._svc_part.do_update(id_, data)

    @api_method(CredentialsDeleteArgs, CredentialsDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> bool:
        """Delete Cloud Sync Credentials of ``id``."""
        await self._svc_part.do_delete(id_)
        return True

    @api_method(CredentialsVerifyArgs, CredentialsVerifyResult, roles=["CLOUD_SYNC_WRITE"])
    def verify(self, provider: CloudCredentialProvider) -> dict[str, Any]:
        """
        Verify if ``attributes`` provided for ``provider`` are authorized by the ``provider``.
        """
        return self._svc_part.verify(provider)

    @api_method(CredentialsS3ProviderChoicesArgs, CredentialsS3ProviderChoicesResult, check_annotations=True)
    async def s3_provider_choices(self) -> dict[str, str]:
        """
        Provide choices for S3 provider ``provider`` field.
        """
        return S3_PROVIDERS
