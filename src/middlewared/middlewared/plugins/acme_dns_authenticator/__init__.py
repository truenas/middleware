from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    ACMEDNSAuthenticatorCreate,
    ACMEDNSAuthenticatorSchema,
    ACMEDNSAuthenticatorUpdate,
    DNSAuthenticatorAuthenticatorSchemasArgs,
    DNSAuthenticatorAuthenticatorSchemasResult,
    DNSAuthenticatorCreateArgs,
    DNSAuthenticatorCreateResult,
    DNSAuthenticatorDeleteArgs,
    DNSAuthenticatorDeleteResult,
    DNSAuthenticatorEntry,
    DNSAuthenticatorUpdateArgs,
    DNSAuthenticatorUpdateResult,
)
from middlewared.service import GenericCRUDService, private

from .crud import DNSAuthenticatorServicePart

if TYPE_CHECKING:
    from middlewared.main import Middleware

    from .authenticators.base import Authenticator


__all__ = ("DNSAuthenticatorService",)


class DNSAuthenticatorService(GenericCRUDService[DNSAuthenticatorEntry]):

    class Config:
        namespace = "acme.dns.authenticator"
        cli_namespace = "system.acme.dns_auth"
        entry = DNSAuthenticatorEntry
        role_prefix = "NETWORK_INTERFACE"
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = DNSAuthenticatorServicePart(self.context)

    @api_method(DNSAuthenticatorCreateArgs, DNSAuthenticatorCreateResult, check_annotations=True)
    async def do_create(self, dns_authenticator_create: ACMEDNSAuthenticatorCreate) -> DNSAuthenticatorEntry:
        """
        Create a DNS Authenticator

        Create a specific DNS Authenticator containing required authentication details for the said
        provider to successfully connect with it.
        """
        return await self._svc_part.do_create(dns_authenticator_create)

    @api_method(DNSAuthenticatorUpdateArgs, DNSAuthenticatorUpdateResult, check_annotations=True)
    async def do_update(self, id_: int, dns_authenticator_update: ACMEDNSAuthenticatorUpdate) -> DNSAuthenticatorEntry:
        """Update DNS Authenticator of `id`."""
        return await self._svc_part.do_update(id_, dns_authenticator_update)

    @api_method(DNSAuthenticatorDeleteArgs, DNSAuthenticatorDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> bool:
        """Delete DNS Authenticator of `id`."""
        return await self._svc_part.do_delete(id_)

    @api_method(
        DNSAuthenticatorAuthenticatorSchemasArgs,
        DNSAuthenticatorAuthenticatorSchemasResult,
        roles=["READONLY_ADMIN"],
        check_annotations=True,
    )
    def authenticator_schemas(self) -> list[ACMEDNSAuthenticatorSchema]:
        """
        Get the schemas for all DNS providers we support for ACME DNS Challenge and the respective
        attributes required for connecting to them while validating a DNS Challenge.
        """
        return self._svc_part.authenticator_schemas()

    @private
    def get_authenticator_internal(self, authenticator_name: str) -> type[Authenticator]:
        return self._svc_part.get_authenticator_internal(authenticator_name)


async def setup(middleware: Middleware) -> None:
    await middleware.call("network.general.register_activity", "acme", "ACME")
