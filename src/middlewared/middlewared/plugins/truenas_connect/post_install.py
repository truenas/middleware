import asyncio
import logging
import uuid

from truenas_connect_utils.status import Status

from middlewared.plugins.crypto_.utils import CERT_TYPE_EXISTING
from middlewared.service import Service

from .utils import CERT_RENEW_DAYS


logger = logging.getLogger('truenas_connect')


class TNCPostInstallService(Service):

    class Config:
        private = True
        namespace = 'tn_connect.post_install'

    async def process(self, post_install_config):
        if 'tnc_config' not in (post_install_config or {}):
            return

        tnc_config = post_install_config['tnc_config']
        if not tnc_config.get('enabled'):
            logger.debug('TNC Post Install: TNC is not enabled')
            return

        if tnc_config.get('initialization_completed') is not True:
            logger.debug(
                'TNC Post Install: TNC initialization not completed, skipping setup%s',
                f'({tnc_config["initialization_error"]})' if tnc_config.get('initialization_error') else ''
            )
            return

        logger.debug('TNC Post Install: TNC initialization completed, setting up TNC')
        cert_id = await self.middleware.call(
            'datastore.insert',
            'system.certificate', {
                'name': f'truenas_connect_{str(uuid.uuid4())[-5:]}',
                'type': CERT_TYPE_EXISTING,
                'certificate': tnc_config['certificate_public_key'],
                'privatekey': tnc_config['certificate_private_key'],
                'renew_days': CERT_RENEW_DAYS,
                'CSR': tnc_config['csr_public_key'],
            }, {'prefix': 'cert_'}
        )
        await self.middleware.call('etc.generate', 'ssl')

        logger.debug('TNC Post Install: TNC certificate saved to database successfully, updating configuration')
        payload = {
            'certificate': cert_id,
            'enabled': True,
            'heartbeat_url': tnc_config['heartbeat_service_base_url'],
        }
        for k in (
            'ips', 'jwt_token', 'registration_details', 'account_service_base_url',
            'leca_service_base_url', 'tnc_base_url',
            'interfaces_ips', 'use_all_interfaces', 'interfaces',
        ):
            payload[k] = tnc_config[k]

        await self.middleware.call(
            'tn_connect.set_status',
            Status.CONFIGURED.name,
            payload,
        )
        logger.debug('TNC Post Install: Triggering task for syncing interface IPs to run after 5 minutes')
        asyncio.get_event_loop().call_later(
            5 * 60,
            lambda: self.middleware.create_task(self.middleware.call('tn_connect.hostname.sync_interface_ips')),
        )
        logger.debug('TNC Post Install: Configuring nginx to consume TNC certificate')
        await self.middleware.call('tn_connect.acme.update_ui_impl')

        logger.debug('TNC Post Install: TNC setup completed successfully')
