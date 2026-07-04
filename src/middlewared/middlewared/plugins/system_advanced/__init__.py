from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Secret

from middlewared.api import api_method
from middlewared.api.base import EmptyDict
from middlewared.api.current import (
    SystemAdvancedEntry,
    SystemAdvancedGetGpuPciChoicesArgs,
    SystemAdvancedGetGpuPciChoicesResult,
    SystemAdvancedLoginBannerArgs,
    SystemAdvancedLoginBannerResult,
    SystemAdvancedNvidiaPresentArgs,
    SystemAdvancedNvidiaPresentResult,
    SystemAdvancedSedGlobalPasswordArgs,
    SystemAdvancedSedGlobalPasswordIsSetArgs,
    SystemAdvancedSedGlobalPasswordIsSetResult,
    SystemAdvancedSedGlobalPasswordResult,
    SystemAdvancedSerialPortChoicesArgs,
    SystemAdvancedSerialPortChoicesResult,
    SystemAdvancedSyslogCertificateAuthorityChoicesArgs,
    SystemAdvancedSyslogCertificateAuthorityChoicesResult,
    SystemAdvancedSyslogCertificateChoicesArgs,
    SystemAdvancedSyslogCertificateChoicesResult,
    SystemAdvancedUpdate,
    SystemAdvancedUpdateArgs,
    SystemAdvancedUpdateGpuPciIdsArgs,
    SystemAdvancedUpdateGpuPciIdsResult,
    SystemAdvancedUpdateResult,
)
from middlewared.service import GenericConfigService, private

from . import gpu as _gpu
from . import nvidia as _nvidia
from . import serial as _serial
from . import syslog as _syslog
from .config import SystemAdvancedConfigServicePart

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ('SystemAdvancedService',)


class SystemAdvancedService(GenericConfigService[SystemAdvancedEntry]):

    class Config:
        namespace = 'system.advanced'
        cli_namespace = 'system.advanced'
        role_prefix = 'SYSTEM_ADVANCED'
        entry = SystemAdvancedEntry
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = SystemAdvancedConfigServicePart(self.context)

    @api_method(SystemAdvancedUpdateArgs, SystemAdvancedUpdateResult, audit='System advanced update',
                check_annotations=True)
    async def do_update(self, data: SystemAdvancedUpdate) -> SystemAdvancedEntry:
        """
        Update System Advanced Service Configuration.
        """
        return await self._svc_part.do_update(data)

    @api_method(
        SystemAdvancedSedGlobalPasswordIsSetArgs,
        SystemAdvancedSedGlobalPasswordIsSetResult,
        roles=['SYSTEM_ADVANCED_READ'],
        check_annotations=True,
    )
    async def sed_global_password_is_set(self) -> bool:
        """Returns a boolean identifying whether or not a global
        SED password has been set."""
        return bool(await self._svc_part.sed_global_password())

    @api_method(
        SystemAdvancedSedGlobalPasswordArgs,
        SystemAdvancedSedGlobalPasswordResult,
        roles=['SYSTEM_ADVANCED_READ'],
        check_annotations=True,
    )
    async def sed_global_password(self) -> Secret[str]:
        """Returns configured global SED password in clear-text if one
        is configured, otherwise an empty string."""
        return Secret[str](await self._svc_part.sed_global_password())

    @api_method(SystemAdvancedLoginBannerArgs, SystemAdvancedLoginBannerResult, authentication_required=False,
                check_annotations=True)
    def login_banner(self) -> str:
        """Returns user set login banner."""
        # NOTE: This endpoint doesn't require authentication because
        # it is used by UI on the login page
        return self._svc_part.login_banner()

    @api_method(
        SystemAdvancedNvidiaPresentArgs,
        SystemAdvancedNvidiaPresentResult,
        roles=['SYSTEM_ADVANCED_READ'],
        check_annotations=True,
    )
    def nvidia_present(self) -> bool:
        """Returns whether a non-isolated NVIDIA GPU is present in the system."""
        return _nvidia.nvidia_present(self.context)

    @api_method(SystemAdvancedSerialPortChoicesArgs, SystemAdvancedSerialPortChoicesResult, roles=['READONLY_ADMIN'],
                check_annotations=True)
    async def serial_port_choices(self) -> dict[str, str]:
        """
        Get available choices for ``serialport``.
        """
        return await _serial.serial_port_choices(self.context)

    @api_method(
        SystemAdvancedSyslogCertificateChoicesArgs,
        SystemAdvancedSyslogCertificateChoicesResult,
        roles=['READONLY_ADMIN'],
        check_annotations=True,
    )
    async def syslog_certificate_choices(self) -> dict[int, str]:
        """
        Return choices of certificates which can be used for ``syslogservers.N.tls_certificate``.
        """
        return await _syslog.syslog_certificate_choices(self.context)

    @api_method(
        SystemAdvancedSyslogCertificateAuthorityChoicesArgs,
        SystemAdvancedSyslogCertificateAuthorityChoicesResult,
        authorization_required=False,
        check_annotations=True,
    )
    async def syslog_certificate_authority_choices(self) -> EmptyDict:
        """
        Return choices of certificate authorities which can be used for ``syslog_tls_certificate_authority``.

        .. deprecated:: 25.10
            This method is no longer used and will be removed after the UI is updated.
        """
        return _syslog.syslog_certificate_authority_choices()

    @api_method(
        SystemAdvancedGetGpuPciChoicesArgs,
        SystemAdvancedGetGpuPciChoicesResult,
        roles=['SYSTEM_ADVANCED_READ'],
        check_annotations=True,
    )
    def get_gpu_pci_choices(self) -> dict[str, Any]:
        """
        This endpoint gives all the gpu pci ids/slots that can be isolated.
        """
        return _gpu.get_gpu_pci_choices(self.context)

    @api_method(
        SystemAdvancedUpdateGpuPciIdsArgs,
        SystemAdvancedUpdateGpuPciIdsResult,
        roles=['SYSTEM_ADVANCED_WRITE'],
        check_annotations=True,
    )
    async def update_gpu_pci_ids(self, isolated_gpu_pci_ids: list[str]) -> None:
        """
        Update the list of GPU PCI IDs isolated from the host system.
        """
        await _gpu.update_gpu_pci_ids(self.context, isolated_gpu_pci_ids)

    @private
    async def validate_isolated_gpus_on_boot(self) -> None:
        await _gpu.validate_isolated_gpus_on_boot(self.context)


async def setup(middleware: Middleware) -> None:
    try:
        await middleware.run_in_thread(_nvidia.configure_nvidia, middleware.services.system.advanced.context)
    except Exception:
        middleware.logger.error('Unhandled exception configuring nvidia', exc_info=True)
