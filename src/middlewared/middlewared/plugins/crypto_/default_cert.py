from middlewared.service import private, Service

from .utils import CERT_TYPE_EXISTING


class CertificateService(Service):

    @private
    async def setup_self_signed_cert_for_ui(self, cert_name):
        config = await self.middleware.call('system.general.config')
        cert, key = await self.middleware.call('cryptokey.generate_self_signed_certificate')

        cert_dict = {
            'certificate': cert,
            'privatekey': key,
            'name': cert_name,
            'type': CERT_TYPE_EXISTING,
        }

        # We use datastore.insert to directly insert in db as jobs cannot be waited for at this point
        id = await self.middleware.call(
            'datastore.insert',
            'system.certificate',
            cert_dict,
            {'prefix': 'cert_'}
        )

        await self.middleware.call('datastore.update', 'system.settings', config['id'], {'stg_guicertificate': id})

        await self.middleware.call('service.start', 'ssl')
        await self.middleware.call('service.reload', 'http')
