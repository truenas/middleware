import datetime

from middlewared.service import periodic, private, Service


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
                {'prefix': self._config.datastore_prefix}
            )

    @private
    async def get_ca_chain(self, ca_id):
        certs = list(
            map(
                lambda item: dict(item, cert_type='CERTIFICATE'),
                await self.middleware.call(
                    'datastore.query',
                    'system.certificate',
                    [['signedby', '=', ca_id]],
                    {'prefix': self._config.datastore_prefix}
                )
            )
        )

        for ca in await self.middleware.call(
            'datastore.query',
            'system.certificateauthority',
            [['signedby', '=', ca_id]],
            {'prefix': self._config.datastore_prefix}
        ):
            certs.extend((await self.get_ca_chain(ca['id'])))

        ca = await self.middleware.call(
            'datastore.query',
            'system.certificateauthority',
            [['id', '=', ca_id]],
            {'prefix': self._config.datastore_prefix, 'get': True}
        )
        ca.update({'cert_type': 'CA'})

        certs.append(ca)
        return certs
