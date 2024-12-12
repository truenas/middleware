import logging

from middlewared.plugins.crypto_.utils import CERT_TYPE_EXISTING
from middlewared.service import CallError, Service
from middlewared.utils.time_utils import utc_now

from .acme_utils import normalize_acme_config
from .cert_utils import generate_csr, get_hostnames_from_hostname_config
from .mixin import TNCAPIMixin
from .status_utils import Status
from .urls import ACME_CONFIG_URL
from .utils import CERT_RENEW_DAYS, get_account_id_and_system_id


logger = logging.getLogger('truenas_connect')


class TNCACMEService(Service, TNCAPIMixin):

    class Config:
        private = True
        namespace = 'tn_connect.acme'

    async def call(self, url, mode, payload=None):
        config = await self.middleware.call('tn_connect.config_internal')
        return await self._call(url, mode, payload=payload, headers=await self.auth_headers(config))

    async def config(self):
        config = await self.middleware.call('tn_connect.config_internal')
        creds = get_account_id_and_system_id(config)
        if not config['enabled'] or creds is None:
            return {
                'error': 'TrueNAS Connect is not enabled or not configured properly',
                'tnc_configured': False,
                'acme_details': {},
            }

        resp = await self.call(ACME_CONFIG_URL.format(account_id=creds['account_id']), 'get')
        resp['acme_details'] = resp.pop('response')
        if resp['error'] is None:
            resp = normalize_acme_config(resp)

        return resp | {
            'tnc_configured': True,
        }

    async def initiate_cert_generation(self):
        logger.debug('Initiating cert generation steps for TNC')
        try:
            cert_details = await self.initiate_cert_generation_impl()
        except Exception:
            logger.error('Failed to complete certificate generation for TNC', exc_info=True)
            await self.middleware.call('tn_connect.set_status', Status.CERT_GENERATION_FAILED.name)
        else:
            cert_id = await self.middleware.call(
                'datastore.insert',
                'system.certificate', {
                    'name': 'TNC',
                    'type': CERT_TYPE_EXISTING,
                    'certificate': cert_details['cert'],
                    'privatekey': cert_details['private_key'],
                    'renew_days': CERT_RENEW_DAYS,
                }, {'prefix': 'cert_'}
            )
            logger.debug('TNC certificate generated successfully')
            await self.middleware.call('tn_connect.set_status', Status.CONFIGURED.name, {'certificate': cert_id})

    async def initiate_cert_generation_impl(self):
        await self.middleware.call('tn_connect.hostname.register_update_ips')
        return await self.create_cert()

    async def create_cert(self):

        hostname_config = await self.middleware.call('tn_connect.hostname.config')
        if hostname_config['error']:
            raise CallError(f'Failed to fetch TNC hostname configuration: {hostname_config["error"]}')

        acme_config = await self.middleware.call('tn_connect.acme.config')
        if acme_config['error']:
            raise CallError(f'Failed to fetch TNC ACME configuration: {acme_config["error"]}')

        logger.debug('Generating CSR for TNC certificate')
        hostnames = get_hostnames_from_hostname_config(hostname_config)
        csr, private_key = generate_csr(hostnames)
        dns_mapping = {f'DNS:{hostname}': None for hostname in hostnames}

        logger.debug('Performing ACME challenge for TNC certificate')
        final_order = await self.middleware.call(
            'acme.issue_certificate_impl', type('dummy_job', (object,), {'set_progress': lambda *args: None})(),
            10, acme_config['acme_details'], csr, dns_mapping,
        )

        return {
            'cert': final_order.fullchain_pem,
            'acme_uri': final_order.uri,
            'private_key': private_key,
        }

    async def revoke_cert(self):
        tnc_config = await self.middleware.call('tn_connect.config_internal')
        certificate = await self.middleware.call('certificate.get_instance', tnc_config['certificate'])
        acme_config = await self.middleware.call('tn_connect.acme.config')
        if acme_config['error']:
            self.logger.error(
                'Failed to fetch TNC ACME configuration when trying to revoke TNC certificate: %r', acme_config['error']
            )
            return

        try:
            await self.middleware.call(
                'acme.revoke_certificate', acme_config['acme_details'], certificate['certificate'],
            )
        except CallError:
            self.logger.error('Failed to revoke TNC certificate', exc_info=True)
        else:
            await self.middleware.call(
                'datastore.update', 'system.certificate', certificate['id'], {
                    'revoked_date': utc_now(),
                }, {'prefix': 'cert_'}
            )
