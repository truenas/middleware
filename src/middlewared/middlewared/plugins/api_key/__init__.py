from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import Secret

from middlewared.api import api_method
from middlewared.api.current import (
    ApiKeyConvertRawKeyArgs,
    ApiKeyConvertRawKeyResult,
    ApiKeyCreate,
    ApiKeyCreateArgs,
    ApiKeyCreateResult,
    ApiKeyDeleteArgs,
    ApiKeyDeleteResult,
    ApiKeyEntry,
    ApiKeyEntryWithKey,
    ApiKeyMyKeysArgs,
    ApiKeyMyKeysResult,
    ApiKeyScramData,
    ApiKeyUpdate,
    ApiKeyUpdateArgs,
    ApiKeyUpdateResult,
)
from middlewared.service import CallError, GenericCRUDService, pass_app, private
from middlewared.utils.types import AuditCallback

from .crud import ApiKeyServicePart
from .internal import authenticate_impl, revoke_impl

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.main import Middleware
    from middlewared.utils.origin import ConnectionOrigin


__all__ = ('ApiKeyService',)


class ApiKeyService(GenericCRUDService[ApiKeyEntry]):

    class Config:
        namespace = 'api_key'
        datastore = 'account.api_key'
        cli_namespace = 'auth.api_key'
        role_prefix = 'API_KEY'
        entry = ApiKeyEntry
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = ApiKeyServicePart(self.context)

    @api_method(
        ApiKeyCreateArgs,
        ApiKeyCreateResult,
        audit='Create API key',
        audit_extended=lambda data: data['name'],
        roles=['READONLY_ADMIN', 'API_KEY_WRITE'],
        pass_app=True,
        check_annotations=True,
    )
    async def do_create(self, app: App, data: ApiKeyCreate) -> ApiKeyEntryWithKey:
        """
        Create an API key.

        `name` is a user-readable name for the key.
        """
        return await self._svc_part.do_create(app, data)

    @api_method(
        ApiKeyUpdateArgs,
        ApiKeyUpdateResult,
        audit='Update API key',
        audit_callback=True,
        roles=['READONLY_ADMIN', 'API_KEY_WRITE'],
        pass_app=True,
        check_annotations=True,
    )
    async def do_update(
        self,
        app: App,
        audit_callback: AuditCallback,
        id_: int,
        data: ApiKeyUpdate,
    ) -> ApiKeyEntryWithKey | ApiKeyEntry:
        """
        Update API Key `id`.

        Specify `reset: true` to reset this API Key.
        """
        return await self._svc_part.do_update(app, audit_callback, id_, data)

    @api_method(
        ApiKeyDeleteArgs,
        ApiKeyDeleteResult,
        audit='Delete API key',
        audit_callback=True,
        roles=['READONLY_ADMIN', 'API_KEY_WRITE'],
        pass_app=True,
        check_annotations=True,
    )
    async def do_delete(
        self,
        app: App,
        audit_callback: AuditCallback,
        id_: int,
    ) -> Literal[True]:
        """
        Delete API Key `id`.
        """
        await self._svc_part.do_delete(app, audit_callback, id_)
        return True

    @api_method(
        ApiKeyMyKeysArgs,
        ApiKeyMyKeysResult,
        roles=['READONLY_ADMIN', 'API_KEY_READ'],
        pass_app=True,
        pass_app_require=True,
        check_annotations=True,
    )
    async def my_keys(self, app: App) -> list[ApiKeyEntry]:
        """Get the existing API keys for the currently authenticated user."""
        if app.authenticated_credentials is None or not app.authenticated_credentials.is_user_session:
            raise CallError('Not a user session')

        username = app.authenticated_credentials.user['username']  # type: ignore[attr-defined]
        return await self._svc_part.query([['username', '=', username]])

    @api_method(
        ApiKeyConvertRawKeyArgs,
        ApiKeyConvertRawKeyResult,
        roles=['API_KEY_READ'],
        check_annotations=True,
    )
    async def convert_raw_key(self, raw_key: Secret[str]) -> ApiKeyScramData:
        """
        Convert a raw API key into its SCRAM authentication components.

        This allows API key consumers to transform a raw API key
        (format: `id-key`) into the precomputed SCRAM authentication
        material for improved performance.

        NOTE: this is a convenience function for API consumers. It does
        not impact the API key stored server-side.
        """
        return await self._svc_part.convert_raw_key(raw_key.get_secret_value())

    @private
    @pass_app(require=True)  # type: ignore[misc]
    async def authenticate(
        self,
        app: App,
        key: str,
        origin: ConnectionOrigin,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        return await authenticate_impl(self.context, app, key, origin)

    @private
    async def revoke(self, key_id: int, reason: str) -> None:
        await revoke_impl(self.context, self._config.datastore, key_id, reason)
