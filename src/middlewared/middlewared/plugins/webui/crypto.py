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
        return await self.middleware.call2(
            self.s.certificate.get_domain_names, cert_id,
        )

    @api_method(
        WebUICryptoCsrProfilesArgs,
        WebUICryptoCsrProfilesResult,
        roles=['CERTIFICATE_READ']
    )
    async def csr_profiles(self):
        """Return predefined CSR profiles for common certificate roles.

        There is a profile for each combination of role (a TLS server certificate, or a TLS
        client certificate used when TrueNAS authenticates itself to a remote service) and key
        type (RSA or EC). Each one provides recommended defaults for the key parameters, the
        digest algorithm, and the X.509 extensions (basic constraints, key usage, extended key
        usage).

        The profiles are advisory: they are intended to prefill the CSR form and are not applied
        by :method:`certificate.create`, which must be passed these values explicitly.
        """
        return CSRProfilesModel().model_dump()
