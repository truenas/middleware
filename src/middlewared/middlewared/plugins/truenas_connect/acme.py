import logging
import uuid

from truenas_connect_utils.acme import acme_config, create_cert
from truenas_connect_utils.exceptions import CallError as TNCCallError
from truenas_connect_utils.status import Status

from middlewared.plugins.crypto_.utils import CERT_TYPE_EXISTING
from middlewared.service import CallError, job, Service

from .utils import CERT_RENEW_DAYS


logger = logging.getLogger('truenas_connect')


class TNCACMEService(Service):

    class Config:
        private = True
        namespace = 'tn_connect.acme'

    async def config(self):
        return await acme_config(await self.middleware.call('tn_connect.config_internal'))

    async def update_ui(self):
        logger.debug('Updating UI with TNC cert')
        try:
            await self.update_ui_impl()
        except Exception:
            logger.error('Failed to configure TNC cert in the UI', exc_info=True)
            await self.middleware.call('tn_connect.set_status', Status.CERT_CONFIGURATION_FAILURE.name)
        else:
            logger.debug('TNC cert configured successfully')
            await self.middleware.call('tn_connect.set_status', Status.CONFIGURED.name)
            logger.debug('Initiating TNC heartbeat')
            self.middleware.create_task(self.middleware.call('tn_connect.heartbeat.start'))
            # Let's restart UI now
            # TODO: Hash this out with everyone
            await self.middleware.call('system.general.ui_restart', 2)

    async def update_ui_impl(self):
        config = await self.middleware.call('tn_connect.config')
        # We are going to set the cert now for system UI
        if config['certificate'] is None:
            # Just some sanity testing
            raise CallError('Certificate is not set for TrueNAS Connect')
        await self.middleware.call('system.general.update', {'ui_certificate': config['certificate']})

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
                    'name': f'truenas_connect_{str(uuid.uuid4())[-5:]}',
                    'type': CERT_TYPE_EXISTING,
                    'certificate': cert_details['cert'],
                    'privatekey': cert_details['private_key'],
                    'renew_days': CERT_RENEW_DAYS,
                    'CSR': cert_details['csr'],
                }, {'prefix': 'cert_'}
            )
            await self.middleware.call('etc.generate', 'ssl')
            logger.debug('TNC certificate generated successfully')
            await self.middleware.call(
                'tn_connect.set_status', Status.CERT_GENERATION_SUCCESS.name, {'certificate': cert_id}
            )
            await self.update_ui()

    async def renew_cert(self):
        logger.debug('Initiating renewal of TNC certificate')
        await self.middleware.call('tn_connect.set_status', Status.CERT_RENEWAL_IN_PROGRESS.name)
        try:
            config = await self.middleware.call('tn_connect.config')
            renewal_job = await self.middleware.call('tn_connect.acme.create_cert', config['certificate'])
            await renewal_job.wait(raise_error=True)
        except Exception:
            logger.error('Failed to renew certificate for TNC', exc_info=True)
            await self.middleware.call('tn_connect.set_status', Status.CERT_RENEWAL_FAILURE.name)
        else:
            logger.debug('TNC certificate renewed successfully, updating database')
            cert_details = renewal_job.result
            await self.middleware.call(
                'datastore.update',
                'system.certificate',
                config['certificate'],
                {'certificate': cert_details['cert']},
                {'prefix': 'cert_'},
            )
            await self.middleware.call('etc.generate', 'ssl')
            await self.middleware.call('tn_connect.set_status', Status.CERT_RENEWAL_SUCCESS.name)
            await self.update_ui()

    async def initiate_cert_generation_impl(self):
        await self.middleware.call('tn_connect.hostname.register_update_ips')
        cert_job = await self.middleware.call('tn_connect.acme.create_cert')
        await cert_job.wait()
        if cert_job.error:
            raise CallError(cert_job.error)

        return cert_job.result

    @job(lock='tn_connect_cert_generation')
    async def create_cert(self, job, cert_id=None):
        csr_details = None
        if cert := (await self.middleware.call('certificate.query', [['id', '=', cert_id]])):
            csr_details = {
                'csr': cert[0]['CSR'],
                'private_key': cert[0]['privatekey'],
            }

        try:
            return await create_cert(await self.middleware.call('tn_connect.config_internal'), csr_details)
        except TNCCallError as e:
            raise CallError(str(e))

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
            logger.error('Failed to revoke TNC certificate', exc_info=True)


async def check_status(middleware):
    tnc_config = await middleware.call('tn_connect.config')
    if tnc_config['status'] == Status.CERT_GENERATION_IN_PROGRESS.name:
        logger.debug('Middleware started and cert generation is in progress, initiating process')
        middleware.create_task(middleware.call('tn_connect.acme.initiate_cert_generation'))
    elif tnc_config['status'] in (
            Status.CERT_GENERATION_SUCCESS.name, Status.CERT_RENEWAL_SUCCESS.name,
    ):
        logger.debug('Middleware started and cert generation is already successful, updating UI')
        middleware.create_task(middleware.call('tn_connect.acme.update_ui'))
    elif tnc_config['status'] == Status.CERT_RENEWAL_IN_PROGRESS.name:
        logger.debug('Middleware started and cert renewal is in progress, initiating process')
        middleware.create_task(middleware.call('tn_connect.acme.renew_cert'))


async def _event_system_ready(middleware, event_type, args):
    await check_status(middleware)


async def setup(middleware):
    middleware.event_subscribe('system.ready', _event_system_ready)
    if await middleware.call('system.ready'):
        await check_status(middleware)
