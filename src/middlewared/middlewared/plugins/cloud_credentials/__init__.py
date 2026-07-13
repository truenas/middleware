from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api import api_method
from middlewared.api.current import (
    CloudCredentialCreate,
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
    CredentialsVerifyData,
    CredentialsVerifyResult,
)
from middlewared.service import GenericCRUDService, private

from . import verify as verify_
from .crud import CloudCredentialModel, CredentialsServicePart  # noqa: F401 (CloudCredentialModel registers the model)
from .verify import PROVIDER_UNION

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("CredentialsService",)


class CredentialsService(GenericCRUDService[CredentialsEntry]):
    _svc_part: CredentialsServicePart

    class Config:
        namespace = "cloudsync.credentials"

        cli_namespace = "task.cloud_sync.credential"

        role_prefix = "CLOUD_SYNC"

        entry = CredentialsEntry
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = CredentialsServicePart(self.context)

    @private
    def extend(self, data: dict[str, Any]) -> dict[str, Any]:
        # Exposed as ``cloudsync.credentials.extend`` for callers that hold a raw datastore row (the cloud
        # sync / cloud backup task extenders) and need the nested, plaintext provider shape.
        return self._svc_part.extend(data, {})

    @api_method(CredentialsVerifyArgs, CredentialsVerifyResult, roles=["CLOUD_SYNC_WRITE"], check_annotations=True)
    def verify(self, data: PROVIDER_UNION) -> CredentialsVerifyData:
        """
        Verify if ``attributes`` provided for ``provider`` are authorized by the ``provider``.
        """
        return verify_.verify(self, data)

    @api_method(CredentialsCreateArgs, CredentialsCreateResult, check_annotations=True)
    async def do_create(self, data: CloudCredentialCreate) -> CredentialsEntry:
        """
        Create Cloud Sync Credentials.
        """
        return await self._svc_part.do_create(data)

    @api_method(CredentialsUpdateArgs, CredentialsUpdateResult, check_annotations=True)
    async def do_update(self, id_: int, data: CloudCredentialUpdate) -> CredentialsEntry:
        """
        Update Cloud Sync Credentials of ``id``.
        """
        return await self._svc_part.do_update(id_, data)

    @api_method(CredentialsDeleteArgs, CredentialsDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> bool:
        """
        Delete Cloud Sync Credentials of ``id``.
        """
        return await self._svc_part.do_delete(id_)

    @api_method(
        CredentialsS3ProviderChoicesArgs,
        CredentialsS3ProviderChoicesResult,
        check_annotations=True,
    )
    def s3_provider_choices(self) -> dict[str, str]:
        """
        Provide choices for S3 provider ``provider`` field.
        """
        return verify_.s3_provider_choices()
