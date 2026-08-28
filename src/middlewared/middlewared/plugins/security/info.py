from subprocess import run

from truenas_pylicensed.features import LicenseFeature

from middlewared.api import api_method
from middlewared.api.current import (
    SystemSecurityInfoFipsAvailableArgs, SystemSecurityInfoFipsAvailableResult,
    SystemSecurityInfoFipsEnabledArgs, SystemSecurityInfoFipsEnabledResult,
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
        """Returns a boolean identifying whether FIPS mode may be toggled on this system"""
        # FIPS mode has no entitlement of its own: the product feature matrix covers it and GPOS
        # STIG mode with a single STIG row. Callers gate every enterprise security option on this,
        # password policy included, so the STIG entitlement governs all of them.
        return self.call_sync2(self.s.truenas.entitlements.check, LicenseFeature.STIG).entitled

    @api_method(
        SystemSecurityInfoFipsEnabledArgs, SystemSecurityInfoFipsEnabledResult,
        roles=['SYSTEM_SECURITY_READ']
    )
    def fips_enabled(self):
        """Returns a boolean identifying whether FIPS mode has been enabled on this system"""
        cp = run(['openssl', 'list', '-providers'], capture_output=True)
        if cp.returncode:
            raise CallError(f'Failed to determine if fips is enabled: {cp.stderr.decode()}')

        return b'OpenSSL FIPS Provider' in cp.stdout
