from middlewared.service import private, Service

from .utils import CERT_TYPE_EXISTING, DEFAULT_CERT_NAME


class CertificateService(Service):

    @private
    async def setup_self_signed_cert_for_ui(self, cert_name=DEFAULT_CERT_NAME):
        cert_id = None
        index = 1
        while not cert_id:
            cert = await self.middleware.call('certificate.query', [['name', '=', cert_name]])
            if cert:
                if await self.middleware.call('certificate.cert_services_validation', cert['id'], 'certificate', False):
                    cert_name = f'{cert_name}_{index}'
                    index += 1
                else:
                    cert_id = cert['id']
                    self.logger.debug('Using %r certificate for System UI', cert_name)
            else:
                cert_id = await self.setup_self_signed_cert_for_ui_impl(cert_name)
                self.logger.debug('Default certificate for System created')

        await self.middleware.call(
            'datastore.update',
            'system.settings',
            (await self.middleware.call('system.general.config'))['id'],
            {'stg_guicertificate': cert_id}
        )

        await self.middleware.call('service.start', 'ssl')
        await self.middleware.call('service.reload', 'http')

    @private
    async def setup_self_signed_cert_for_ui_impl(self, cert_name):
        cert, key = await self.middleware.call('cryptokey.generate_self_signed_certificate')

        cert_dict = {
            'certificate': cert,
            'privatekey': key,
            'name': cert_name,
            'type': CERT_TYPE_EXISTING,
        }

        # We use datastore.insert to directly insert in db as this is a self-signed cert
        # and we don't allow that via regular api
        return await self.middleware.call(
            'datastore.insert',
            'system.certificate',
            cert_dict,
            {'prefix': 'cert_'}
        )
