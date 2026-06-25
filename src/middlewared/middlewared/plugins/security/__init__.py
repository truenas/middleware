from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    SystemSecurityEntry,
    SystemSecurityUpdate,
    SystemSecurityUpdateArgs,
    SystemSecurityUpdateResult,
)
from middlewared.service import GenericConfigService, job, private

from .config import SystemSecurityConfigServicePart
from .info import SystemSecurityInfoService
from .sessions import SystemSecuritySessionsService
from .stig import configure_fips as configure_fips_impl
from .stig import configure_stig as configure_stig_impl

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware

__all__ = ('SystemSecurityService',)


class SystemSecurityService(GenericConfigService[SystemSecurityEntry]):

    class Config:
        cli_namespace = 'system.security'
        namespace = 'system.security'
        entry = SystemSecurityEntry
        role_prefix = 'SYSTEM_SECURITY'
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self.info = SystemSecurityInfoService(middleware)
        self.sessions = SystemSecuritySessionsService(middleware)
        self._svc_part = SystemSecurityConfigServicePart(self.context)

    @api_method(
        SystemSecurityUpdateArgs, SystemSecurityUpdateResult,
        audit='System security update',
        check_annotations=True,
    )
    @job(lock='security_update')
    async def do_update(self, job: Job, data: SystemSecurityUpdate) -> SystemSecurityEntry:
        """
        Update System Security Service Configuration.

        This method is used to change the FIPS, STIG, and local account
        policies for TrueNAS Enterprise. These features are not
        available in community editions of TrueNAS.
        """
        return await self._svc_part.do_update(job, data)

    @private
    async def configure_stig(self, data: SystemSecurityEntry | None = None) -> None:
        await configure_stig_impl(self.context, data)

    @private
    def configure_fips(self, database_path: str | None = None) -> None:
        configure_fips_impl(self.context, database_path)


async def on_config_upload(middleware: Middleware, path: str) -> None:
    await middleware.call2(middleware.services.system.security.configure_fips, path)


async def setup(middleware: Middleware) -> None:
    middleware.register_hook('config.on_upload', on_config_upload, sync=True)

    await middleware.call2(middleware.services.system.security.configure_stig)
