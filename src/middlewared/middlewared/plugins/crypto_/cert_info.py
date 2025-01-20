from middlewared.api import api_method
from middlewared.api.current import (
    CertificateCountryChoicesArgs,
    CertificateCountryChoicesResult,
    CertificateAcmeServerChoicesArgs,
    CertificateAcmeServerChoicesResult,
    CertificateECCurveChoicesArgs,
    CertificateECCurveChoicesResult,
    CertificateExtendedKeyUsageChoicesArgs,
    CertificateExtendedKeyUsageChoicesResult,
)
from middlewared.service import private, Service
from middlewared.utils.country_codes import get_country_codes

from .utils import EC_CURVES, EKU_OIDS


class CertificateService(Service):

    class Config:
        cli_namespace = 'system.certificate'

    @private
    async def get_domain_names(self, cert_id):
        data = await self.middleware.call('certificate.get_instance', int(cert_id))
        names = [data['common']] if data['common'] else []
        names.extend(data['san'])
        return names

    @api_method(
        CertificateCountryChoicesArgs,
        CertificateCountryChoicesResult,
        roles=['CERTIFICATE_READ']
    )
    def country_choices(self):
        """Returns country choices for creating a certificate/csr."""
        return get_country_codes()

    @api_method(
        CertificateAcmeServerChoicesArgs,
        CertificateAcmeServerChoicesResult,
        roles=['CERTIFICATE_READ']
    )
    async def acme_server_choices(self):
        """
        Dictionary of popular ACME Servers with their directory URI
        endpoints which we display automatically in the UI
        """
        return {
            'https://acme-staging-v02.api.letsencrypt.org/directory': 'Let\'s Encrypt Staging Directory',
            'https://acme-v02.api.letsencrypt.org/directory': 'Let\'s Encrypt Production Directory'
        }

    @api_method(
        CertificateECCurveChoicesArgs,
        CertificateECCurveChoicesResult,
        roles=['CERTIFICATE_READ']
    )
    async def ec_curve_choices(self):
        """Dictionary of supported EC curves."""
        return {k: k for k in EC_CURVES}

    @api_method(
        CertificateExtendedKeyUsageChoicesArgs,
        CertificateExtendedKeyUsageChoicesResult,
        roles=['CERTIFICATE_READ']
    )
    async def extended_key_usage_choices(self):
        """
        Dictionary of names that can be used in the
        ExtendedKeyUsage attribute of a certificate request.
        """
        return {k: k for k in EKU_OIDS}
