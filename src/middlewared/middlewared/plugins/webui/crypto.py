from middlewared.api import api_method
from middlewared.api.current import (
    CAProfilesArgs,
    CAProfilesModel,
    CAProfilesResult,
    CertProfilesArgs,
    CertProfilesModel,
    CertProfilesResult,
    CSRProfilesArgs,
    CSRProfilesModel,
    CSRProfilesResult,
)
from middlewared.schema import accepts, Int
from middlewared.service import Service


class WebUICryptoService(Service):

    class Config:
        namespace = 'webui.crypto'
        private = True
        cli_private = True

    @api_method(
        CertProfilesArgs,
        CertProfilesResult,
        roles=['READONLY_ADMIN']
    )
    async def certificate_profiles(self):
        return CertProfilesModel().model_dump(by_alias=True)

    @api_method(
        CAProfilesArgs,
        CAProfilesResult,
        roles=['READONLY_ADMIN']
    )
    async def certificateauthority_profiles(self):
        return CAProfilesModel().model_dump(by_alias=True)

    @accepts(Int('cert_id'), roles=['READONLY_ADMIN'])
    async def get_certificate_domain_names(self, cert_id):
        return await self.middleware.call('certificate.get_domain_names', cert_id)

    @api_method(
        CSRProfilesArgs,
        CSRProfilesResult,
        roles=['READONLY_ADMIN']
    )
    async def csr_profiles(self):
        return CSRProfilesModel().model_dump(by_alias=True)
