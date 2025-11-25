import logging
import uuid
from datetime import datetime, timezone

from truenas_acme_utils.ari import fetch_renewal_info
from truenas_connect_utils.acme import acme_config, create_cert
from truenas_connect_utils.exceptions import CallError as TNCCallError
from truenas_connect_utils.status import Status
from truenas_crypto_utils.read import get_cert_id

from middlewared.plugins.crypto_.utils import CERT_TYPE_EXISTING
from middlewared.service import CallError, job, Service

from .utils import CERT_RENEW_DAYS, TNC_CERT_PREFIX


logger = logging.getLogger('truenas_connect')


class TNCACMEService(Service):

    class Config:
        private = True
        namespace = 'tn_connect.acme'

    async def config(self):
        return await acme_config(await self.middleware.call('tn_connect.config_internal'))

    async def update_ui(self, start_heartbeat=True):
        logger.debug('Updating UI with TNC cert')
        config = await self.middleware.call('tn_connect.config')
        if config['certificate'] is None:
            # Just some sanity testing
            logger.error('TNC cert configuration failed')
            await self.middleware.call('tn_connect.set_status', Status.CERT_CONFIGURATION_FAILURE.name)
        else:
            logger.debug('TNC cert configured successfully')
            await self.middleware.call('tn_connect.set_status', Status.CONFIGURED.name)
            logger.debug('Initiating TNC heartbeat')
            self.middleware.create_task(self.middleware.call('tn_connect.heartbeat.start'))
            # Let's restart UI now
            # TODO: Hash this out with everyone
            await self.middleware.call('system.general.ui_restart', 2)
            if await self.middleware.call('failover.licensed'):
                # We would like to make sure nginx is reloaded on the remote controller as well
                logger.debug('Restarting UI on remote controller')
                try:
                    await self.middleware.call(
                        'failover.call_remote', 'system.general.ui_restart', [2],
                        {'raise_connect_error': False, 'timeout': 2, 'connect_timeout': 2}
                    )
                except Exception:
                    logger.error('Failed to restart UI on remote controller', exc_info=True)

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
                    'name': f'{TNC_CERT_PREFIX}{str(uuid.uuid4())[-5:]}',
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

    async def renew_cert(self, bypass_renewal_check=False):
        cert_renewal_id = None
        if not bypass_renewal_check:
            renewal_needed, cert_renewal_id = await self.middleware.call('tn_connect.acme.check_renewal_needed')
            if not renewal_needed:
                logger.debug('TNC certificate renewal not needed at this time')
                return

        logger.debug('Initiating renewal of TNC certificate')
        await self.middleware.call('tn_connect.set_status', Status.CERT_RENEWAL_IN_PROGRESS.name)
        try:
            config = await self.middleware.call('tn_connect.config')
            renewal_job = await self.middleware.call(
                'tn_connect.acme.create_cert', config['certificate'], cert_renewal_id
            )
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
            await self.update_ui(False)

    def check_renewal_needed(self):
        # checks if renewal is needed and returns a tuple i.e bool/str with former indicating if renewal is needed
        # and latter showing the cert id
        logger.debug('Checking renewal of TNC certificate is needed')
        config = self.middleware.call_sync('tn_connect.config')
        if config['certificate'] is None:
            logger.debug('No TNC certificate configured, skipping renewal check')
            return False, None

        certificate = self.middleware.call_sync('certificate.get_instance', config['certificate'])
        try:
            cert_id = get_cert_id(certificate['certificate'])
        except Exception:
            logger.error('Failed to parse TNC certificate to get its ID', exc_info=True)
            # This should not happen, but if it does
            # what this means is that there are 5 days left till the cert expires and for some X reason we
            # were not able to parse the cert id and in this case, let's just go ahead and renew the cert
            # without factoring in the ARI as we were not able to parse the cert id
            # This either should not happen or will be a rare occurrence
            return True, None

        acme_config = self.middleware.call_sync('tn_connect.acme.config')
        if acme_config['error']:
            logger.error(
                'Failed to fetch TNC ACME configuration when checking renewal: %r', acme_config['error']
            )
            return False, None

        renewal_info = fetch_renewal_info(acme_config['acme_details']['renewal_info'], cert_id)
        if renewal_info['error']:
            logger.error('Failed to fetch renewal info for TNC certificate: %r', renewal_info['error'])
            return False, None

        start_time = renewal_info['suggested_window']['start']
        end_time = renewal_info['suggested_window']['end']

        logger.debug(
            'TNC renewal suggested window: %s to %s',
            start_time.strftime('%Y-%m-%d %H:%M:%S UTC'),
            end_time.strftime('%Y-%m-%d %H:%M:%S UTC')
        )

        # Check if current time is within the suggested renewal window
        current_time = datetime.now(timezone.utc)
        # We deliberately ignore end_time as per RFC 9773 Section 4.2
        within_window = start_time <= current_time
        if within_window:
            logger.info(
                'Renewal needed: current time (%s) is past renewal start (%s)',
                current_time.strftime('%Y-%m-%d %H:%M:%S UTC'),
                start_time.strftime('%Y-%m-%d %H:%M:%S UTC')
            )
        else:
            time_until_renewal = start_time - current_time
            days = time_until_renewal.days
            hours = time_until_renewal.seconds // 3600
            logger.debug(
                'Renewal not needed: %d days and %d hours until renewal window opens at %s',
                days, hours, start_time.strftime('%Y-%m-%d %H:%M:%S UTC')
            )

        return within_window, cert_id

    async def initiate_cert_generation_impl(self):
        cert_job = await self.middleware.call('tn_connect.acme.create_cert')
        await cert_job.wait()
        if cert_job.error:
            raise CallError(cert_job.error)

        return cert_job.result

    @job(lock='tn_connect_cert_generation')
    async def create_cert(self, job, cert_id=None, cert_renewal_id=None):
        csr_details = None
        if cert := (await self.middleware.call('certificate.query', [['id', '=', cert_id]])):
            csr_details = {
                'csr': cert[0]['CSR'],
                'private_key': cert[0]['privatekey'],
            }

        await self.middleware.call('tn_connect.hostname.register_update_ips', None, True)
        try:
            return await create_cert(
                await self.middleware.call('tn_connect.config_internal'), csr_details, cert_renewal_id
            )
        except TNCCallError as e:
            raise CallError(str(e))

    async def revoke_cert(self):
        tnc_config = await self.middleware.call('tn_connect.config_internal')
        if tnc_config['certificate'] is None:
            # If cert generation had failed, there won't be any cert to revoke
            logger.debug('No TNC certificate configured, skipping revocation')
            return

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
    if not await middleware.call('failover.is_single_master_node'):
        return

    await middleware.call('tn_connect.state.check')


async def _event_system_ready(middleware, event_type, args):
    if not await middleware.call('system.is_ha_capable'):
        # For HA systems, failover logic will handle this
        await check_status(middleware)


async def setup(middleware):
    middleware.event_subscribe('system.ready', _event_system_ready)
    if await middleware.call('system.ready'):
        await check_status(middleware)
