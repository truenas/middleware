from middlewared.api import api_method
from middlewared.api.current import (
    CSRProfilesModel,
    WebUICryptoCsrProfilesArgs,
    WebUICryptoCsrProfilesResult,
    WebUICryptoGetCertificateDomainNamesArgs,
    WebUICryptoGetCertificateDomainNamesResult,
)
from middlewared.service import Service


class WebUICryptoService(Service):

    class Config:
        namespace = 'webui.crypto'
        cli_private = True

    @api_method(
        WebUICryptoGetCertificateDomainNamesArgs,
        WebUICryptoGetCertificateDomainNamesResult,
        roles=['READONLY_ADMIN']
    )
    async def get_certificate_domain_names(self, cert_id):
        """Return the domain names associated with a certificate.

        This includes the Common Name (if set) followed by any Subject Alternative
        Names (SANs).
        """
        return await self.middleware.call('certificate.get_domain_names', cert_id)

    @api_method(
        WebUICryptoCsrProfilesArgs,
        WebUICryptoCsrProfilesResult,
        roles=['CERTIFICATE_READ']
    )
    async def csr_profiles(self):
        """Return predefined CSR profiles for common certificate types.

        Each profile provides recommended defaults for key type, key length or
        curve, lifetime, digest algorithm, and X.509 extensions (basic constraints,
        key usage, extended key usage).
        """
        return CSRProfilesModel().model_dump(by_alias=True)
