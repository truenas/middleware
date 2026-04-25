from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method, Event
from middlewared.api.current import (
    TrueNASConnectEntry,
    TrueNASConnectUpdate, TrueNASConnectUpdateArgs, TrueNASConnectUpdateResult,
    TrueNASConnectGetRegistrationUriArgs, TrueNASConnectGetRegistrationUriResult,
    TrueNASConnectGenerateClaimTokenArgs, TrueNASConnectGenerateClaimTokenResult,
    TrueNASConnectIpsWithHostnamesArgs, TrueNASConnectIpsWithHostnamesResult,
    TrueNASConnectConfigChangedEvent,
)
from middlewared.service import GenericConfigService

from .acme import TNCACMEService, _event_system_ready, check_status
from .cert_attachment import TNCCertificateAttachment
from .config import TrueNASConnectConfigServicePart
from .finalize_registration import TNCRegistrationFinalizeService
from .heartbeat import TNCHeartbeatService
from .hostname import TNCHostnameService, on_general_config_update, update_ips
from .post_install import TNCPostInstallService
from .private_models import (
    TrueNASConnectUpdateEnvironment,
    TrueNASConnectUpdateEnvironmentArgs, TrueNASConnectUpdateEnvironmentResult,
)
from .register import generate_claim_token_impl, get_registration_uri_impl
from .state import TrueNASConnectStateService

if TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ('TrueNASConnectService',)


class TrueNASConnectService(GenericConfigService[TrueNASConnectEntry]):

    class Config:
        cli_private = True
        namespace = 'tn_connect'
        entry = TrueNASConnectEntry
        role_prefix = 'TRUENAS_CONNECT'
        generic = True
        events = [
            Event(
                name='tn_connect.config',
                description='Sent on TrueNAS Connect configuration changes',
                roles=['TRUENAS_CONNECT_READ'],
                models={'CHANGED': TrueNASConnectConfigChangedEvent},
            ),
        ]

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self.acme = TNCACMEService(middleware)
        self.finalize = TNCRegistrationFinalizeService(middleware)
        self.heartbeat = TNCHeartbeatService(middleware)
        self.hostname = TNCHostnameService(middleware)
        self.post_install = TNCPostInstallService(middleware)
        self.state = TrueNASConnectStateService(middleware)
        self._svc_part = TrueNASConnectConfigServicePart(self.context)

    @api_method(
        TrueNASConnectUpdateArgs, TrueNASConnectUpdateResult,
        audit='TrueNAS Connect: Updating configuration', check_annotations=True,
    )
    async def do_update(self, data: TrueNASConnectUpdate) -> TrueNASConnectEntry:
        """Update TrueNAS Connect configuration."""
        return await self._svc_part.do_update(data)

    @api_method(
        TrueNASConnectGenerateClaimTokenArgs, TrueNASConnectGenerateClaimTokenResult,
        roles=['TRUENAS_CONNECT_WRITE'],
        audit='TrueNAS Connect: Generating claim token',
        check_annotations=True,
    )
    async def generate_claim_token(self) -> str:
        """
        Generate a claim token for TrueNAS Connect.

        This is used to claim the system with TrueNAS Connect. When this endpoint will be called, a token will
        be generated which will be used to assist with initial setup with truenas connect.
        """
        return await generate_claim_token_impl(self.context)

    @api_method(
        TrueNASConnectGetRegistrationUriArgs, TrueNASConnectGetRegistrationUriResult,
        roles=['TRUENAS_CONNECT_READ'], check_annotations=True,
    )
    async def get_registration_uri(self) -> str:
        """
        Return the registration URI for TrueNAS Connect.

        Before this endpoint is called, tn_connect must be enabled and a claim token must be generated - based
        off which this endpoint will return the registration URI for TrueNAS Connect.
        """
        return await get_registration_uri_impl(self.context)

    @api_method(
        TrueNASConnectIpsWithHostnamesArgs, TrueNASConnectIpsWithHostnamesResult,
        roles=['TRUENAS_CONNECT_READ'], check_annotations=True,
    )
    async def ips_with_hostnames(self) -> dict[str, str]:
        """Returns current mapping of ips configured with truenas connect against their hostnames."""
        hostname_config = await self.call2(self.s.tn_connect.hostname.config)
        if hostname_config['error'] is None and hostname_config['hostname_configured']:
            return {v: k for k, v in hostname_config['hostname_details'].items()}
        return {}

    @api_method(
        TrueNASConnectUpdateEnvironmentArgs, TrueNASConnectUpdateEnvironmentResult,
        private=True, check_annotations=True,
    )
    async def update_environment(self, data: TrueNASConnectUpdateEnvironment) -> TrueNASConnectEntry:
        return await self._svc_part.update_environment(data)


async def setup(middleware: Middleware) -> None:
    middleware.event_subscribe('system.ready', _event_system_ready)
    middleware.event_subscribe('ipaddress.change', update_ips)
    middleware.register_hook('system.general.post_update', on_general_config_update)
    await middleware.call(
        'certificate.register_attachment_delegate', TNCCertificateAttachment(middleware),
    )
    if await middleware.call('system.ready'):
        await check_status(middleware)
