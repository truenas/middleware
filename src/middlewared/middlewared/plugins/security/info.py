from subprocess import run

from truenas_pylicensed import LicenseType

from middlewared.api import api_method
from middlewared.api.current import (
    SystemSecurityInfoFipsAvailableArgs,
    SystemSecurityInfoFipsAvailableResult,
    SystemSecurityInfoFipsEnabledArgs,
    SystemSecurityInfoFipsEnabledResult,
)
from middlewared.service import CallError, Service


class SystemSecurityInfoService(Service):

    class Config:
        namespace = 'system.security.info'
        cli_namespace = 'system.security.info'

    @api_method(
        SystemSecurityInfoFipsAvailableArgs, SystemSecurityInfoFipsAvailableResult,
        roles=['SYSTEM_SECURITY_READ']
    )
    def fips_available(self):
        """Returns a boolean identifying whether FIPS mode may be toggled on this system."""
        # FIPS/STIG is an iX-licensed-hardware capability: enterprise and legacy (freenas-certified)
        # licenses are ENTERPRISE_* typed; commercial/community software licenses are not and must
        # not unlock it
        info = self.call_sync2(self.s.truenas.license.info_private)
        return info is not None and info.type in (LicenseType.ENTERPRISE_SINGLE, LicenseType.ENTERPRISE_HA)

    @api_method(
        SystemSecurityInfoFipsEnabledArgs, SystemSecurityInfoFipsEnabledResult,
        roles=['SYSTEM_SECURITY_READ']
    )
    def fips_enabled(self):
        """Returns a boolean identifying whether FIPS mode has been enabled on this system."""
        cp = run(['openssl', 'list', '-providers'], capture_output=True)
        if cp.returncode:
            raise CallError(f'Failed to determine if fips is enabled: {cp.stderr.decode()}')

        return b'OpenSSL FIPS Provider' in cp.stdout
