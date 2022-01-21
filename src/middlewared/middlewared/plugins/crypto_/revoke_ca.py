import datetime

from middlewared.service import periodic, private, Service

from .query_utils import get_ca_chain


class CertificateAuthorityService(Service):

    class Config:
        cli_namespace = 'system.certificate.authority'

    @periodic(86400, run_on_start=True)
    @private
    async def crl_generation(self):
        await self.middleware.call('service.start', 'ssl')

    @private
    async def revoke_ca_chain(self, ca_id):
        chain = await self.get_ca_chain(ca_id)
        for cert in chain:
            datastore = f'system.certificate{"authority" if cert["cert_type"] == "CA" else ""}'
            await self.middleware.call(
                'datastore.update',
                datastore,
                cert['id'], {
                    'revoked_date': datetime.datetime.utcnow()
                },
                {'prefix': 'cert_'}
            )

    @private
    async def get_ca_chain(self, ca_id):
        certs = await self.middleware.call('datastore.query', 'system.certificate', [], {'prefix': 'cert_'})
        cas = await self.middleware.call('datastore.query', 'system.certificateauthority', [], {'prefix': 'cert_'})
        return get_ca_chain(ca_id, certs, cas)
