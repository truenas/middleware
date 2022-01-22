from .utils import CERT_TYPE_EXISTING


async def setup(middleware):
    failure = False
    try:
        system_general_config = await middleware.call('system.general.config')
        system_cert = system_general_config['ui_certificate']
        certs = await middleware.call('datastore.query', 'system.certificate', [], {'prefix': 'cert_'})
    except Exception as e:
        failure = True
        middleware.logger.error(f'Failed to retrieve certificates: {e}', exc_info=True)

    if not failure and (not system_cert or system_cert['id'] not in [c['id'] for c in certs]):
        # create a self signed cert if it doesn't exist and set ui_certificate to it's value
        try:
            if not any('freenas_default' == c['name'] for c in certs):
                cert, key = await middleware.call('cryptokey.generate_self_signed_certificate')

                cert_dict = {
                    'certificate': cert,
                    'privatekey': key,
                    'name': 'freenas_default',
                    'type': CERT_TYPE_EXISTING,
                }

                # We use datastore.insert to directly insert in db as jobs cannot be waited for at this point
                id = await middleware.call(
                    'datastore.insert',
                    'system.certificate',
                    cert_dict,
                    {'prefix': 'cert_'}
                )

                await middleware.call('service.start', 'ssl')

                middleware.logger.debug('Default certificate for System created')
            else:
                id = [c['id'] for c in certs if c['name'] == 'freenas_default'][0]
                await middleware.call('certificate.cert_services_validation', id, 'certificate')

            await middleware.call(
                'datastore.update', 'system.settings', system_general_config['id'], {'stg_guicertificate': id}
            )
        except Exception as e:
            failure = True
            middleware.logger.debug(
                'Failed to set certificate for system.general plugin: %s', e, exc_info=True
            )

    if not failure:
        middleware.logger.debug('Certificate setup for System complete')
