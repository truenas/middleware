from middlewared.api import api_method
from middlewared.api.current import (
    WebUICryptoCsrProfilesArgs,
    CSRProfilesModel,
    WebUICryptoCsrProfilesResult,
    WebUICryptoGetCertificateDomainNamesArgs,
    WebUICryptoGetCertificateDomainNamesResult,
)
from middlewared.service import Service


class WebUICryptoService(Service):

    class Config:
        namespace = 'webui.crypto'
        private = True
        cli_private = True

    @api_method(
        WebUICryptoGetCertificateDomainNamesArgs,
        WebUICryptoGetCertificateDomainNamesResult,
        roles=['READONLY_ADMIN']
    )
    async def get_certificate_domain_names(self, cert_id):
        return await self.middleware.call('certificate.get_domain_names', cert_id)

    @api_method(
        WebUICryptoCsrProfilesArgs,
        WebUICryptoCsrProfilesResult,
        roles=['CERTIFICATE_READ']
    )
    async def csr_profiles(self):
        return CSRProfilesModel().model_dump(by_alias=True)
