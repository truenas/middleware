from middlewared.schema import accepts, Int
from middlewared.service import Service


class WebUICryptoService(Service):

    class Config:
        namespace = 'webui.crypto'
        private = True
        cli_private = True

    @accepts(roles=['READONLY'])
    async def certificate_profiles(self):
        return await self.middleware.call('certificate.profiles')

    @accepts(roles=['READONLY'])
    async def certificateauthority_profiles(self):
        return await self.middleware.call('certificateauthority.profiles')

    @accepts(Int('cert_id'), roles=['READONLY'])
    async def get_certificate_domain_names(self, cert_id):
        return await self.middleware.call('certificate.get_domain_names', cert_id)
