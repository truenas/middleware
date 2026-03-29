from __future__ import annotations

from typing import Any, TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    ACMEDNSAuthenticatorCreate,
    ACMEDNSAuthenticatorUpdate,
    DNSAuthenticatorEntry,
    DNSAuthenticatorCreateArgs,
    DNSAuthenticatorCreateResult,
    DNSAuthenticatorUpdateArgs,
    DNSAuthenticatorUpdateResult,
    DNSAuthenticatorDeleteArgs,
    DNSAuthenticatorDeleteResult,
    DNSAuthenticatorAuthenticatorSchemasArgs,
    DNSAuthenticatorAuthenticatorSchemasResult,
)
from middlewared.service import GenericCRUDService, private

from .crud import DNSAuthenticatorServicePart

if TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ('DNSAuthenticatorService',)


class DNSAuthenticatorService(GenericCRUDService[DNSAuthenticatorEntry]):

    class Config:
        namespace = 'acme.dns.authenticator'
        cli_namespace = 'system.acme.dns_auth'
        entry = DNSAuthenticatorEntry
        role_prefix = 'NETWORK_INTERFACE'
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = DNSAuthenticatorServicePart(self.context)

    @api_method(DNSAuthenticatorCreateArgs, DNSAuthenticatorCreateResult, check_annotations=True)
    async def do_create(self, data: ACMEDNSAuthenticatorCreate) -> DNSAuthenticatorEntry:
        """
        Create a DNS Authenticator

        Create a specific DNS Authenticator containing required authentication details for the said
        provider to successfully connect with it.
        """
        return await self._svc_part.do_create(data)

    @api_method(DNSAuthenticatorUpdateArgs, DNSAuthenticatorUpdateResult, check_annotations=True)
    async def do_update(self, id_: int, data: ACMEDNSAuthenticatorUpdate) -> DNSAuthenticatorEntry:
        """Update DNS Authenticator of `id`."""
        return await self._svc_part.do_update(id_, data)

    @api_method(DNSAuthenticatorDeleteArgs, DNSAuthenticatorDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> bool:
        """Delete DNS Authenticator of `id`."""
        return await self._svc_part.do_delete(id_)

    @api_method(
        DNSAuthenticatorAuthenticatorSchemasArgs,
        DNSAuthenticatorAuthenticatorSchemasResult,
        roles=['READONLY_ADMIN'],
        check_annotations=True,
    )
    def authenticator_schemas(self) -> list[dict[str, Any]]:
        """
        Get the schemas for all DNS providers we support for ACME DNS Challenge and the respective
        attributes required for connecting to them while validating a DNS Challenge.
        """
        return self._svc_part.authenticator_schemas()

    @private
    def get_authenticator_internal(self, authenticator_name: str) -> Any:
        return self._svc_part.get_authenticator_internal(authenticator_name)

    @private
    def get_authenticator_schemas(self) -> dict[str, Any]:
        return self._svc_part.get_authenticator_schemas()


async def setup(middleware: Middleware) -> None:
    await middleware.call('network.general.register_activity', 'acme', 'ACME')
