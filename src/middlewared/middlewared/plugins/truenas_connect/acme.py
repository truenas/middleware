from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, cast, TYPE_CHECKING

from truenas_acme_utils.ari import fetch_renewal_info
from truenas_connect_utils.acme import acme_config, create_cert
from truenas_connect_utils.exceptions import CallError as TNCCallError
from truenas_connect_utils.status import Status
from truenas_crypto_utils.read import get_cert_id

from middlewared.plugins.crypto_.utils import CERT_TYPE_EXISTING
from middlewared.service import CallError, job, private, Service

from .internal import config_internal, set_status
from .utils import CERT_RENEW_DAYS, TNC_CERT_PREFIX

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


logger = logging.getLogger('truenas_connect')


class TNCACMEService(Service):

    class Config:
        private = True
        namespace = 'tn_connect.acme'

    @private
    async def config(self) -> dict[str, Any]:
        return cast(dict[str, Any], await acme_config(await config_internal(self.context)))

    @private
    async def update_ui(self, start_heartbeat: bool = True) -> None:
        logger.debug('Updating UI with TNC cert')
        config = await self.call2(self.s.tn_connect.config)
        if config.certificate is None:
            # Just some sanity testing
            logger.error('TNC cert configuration failed')
            await set_status(self.context, Status.CERT_CONFIGURATION_FAILURE.name)
        else:
            logger.debug('TNC cert configured successfully')
            await set_status(self.context, Status.CONFIGURED.name)
            if start_heartbeat:
                logger.debug('Initiating TNC heartbeat')
                self.middleware.create_task(self.call2(self.s.tn_connect.heartbeat_start))
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

    @private
    async def initiate_cert_generation(self) -> None:
        logger.debug('Initiating cert generation steps for TNC')
        try:
            cert_details = await self.initiate_cert_generation_impl()
        except Exception:
            logger.error('Failed to complete certificate generation for TNC', exc_info=True)
            await set_status(self.context, Status.CERT_GENERATION_FAILED.name)
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
            await set_status(
                self.context, Status.CERT_GENERATION_SUCCESS.name, {'certificate': cert_id},
            )
            await self.update_ui()

    @private
    async def renew_cert(self, bypass_renewal_check: bool = False) -> None:
        cert_renewal_id: str | None = None
        if not bypass_renewal_check:
            renewal_needed, cert_renewal_id = await self.call2(
                self.s.tn_connect.acme.check_renewal_needed,
            )
            if not renewal_needed:
                logger.debug('TNC certificate renewal not needed at this time')
                return

        logger.debug('Initiating renewal of TNC certificate')
        await set_status(self.context, Status.CERT_RENEWAL_IN_PROGRESS.name)
        try:
            config = await self.call2(self.s.tn_connect.config)
            renewal_job = await self.call2(
                self.s.tn_connect.acme.create_cert, config.certificate, cert_renewal_id,
            )
            await renewal_job.wait(raise_error=True)
        except Exception:
            logger.error('Failed to renew certificate for TNC', exc_info=True)
            await set_status(self.context, Status.CERT_RENEWAL_FAILURE.name)
        else:
            logger.debug('TNC certificate renewed successfully, updating database')
            # renewal_job.wait(raise_error=True) above guarantees a successful result.
            cert_details = cast(dict[str, Any], renewal_job.result)
            await self.middleware.call(
                'datastore.update',
                'system.certificate',
                config.certificate,
                {'certificate': cert_details['cert']},
                {'prefix': 'cert_'},
            )
            await self.middleware.call('etc.generate', 'ssl')
            await set_status(self.context, Status.CERT_RENEWAL_SUCCESS.name)
            await self.update_ui(False)

    @private
    def check_renewal_needed(self) -> tuple[bool, str | None]:
        # checks if renewal is needed and returns a tuple i.e bool/str with former indicating if renewal is needed
        # and latter showing the cert id
        logger.debug('Checking renewal of TNC certificate is needed')
        config = self.call_sync2(self.s.tn_connect.config)
        if config.certificate is None:
            logger.debug('No TNC certificate configured, skipping renewal check')
            return False, None

        # certificate plugin is unconverted — returns a plain dict, keep dict access
        certificate = self.middleware.call_sync('certificate.get_instance', config.certificate)
        try:
            cert_id: str = get_cert_id(certificate['certificate'])
        except Exception:
            logger.error('Failed to parse TNC certificate to get its ID', exc_info=True)
            # This should not happen, but if it does
            # what this means is that there are 5 days left till the cert expires and for some X reason we
            # were not able to parse the cert id and in this case, let's just go ahead and renew the cert
            # without factoring in the ARI as we were not able to parse the cert id
            # This either should not happen or will be a rare occurrence
            return True, None

        # acme_config returns a dict from truenas_connect_utils.acme — keep dict access
        acme_cfg = self.call_sync2(self.s.tn_connect.acme.config)
        if acme_cfg['error']:
            logger.error(
                'Failed to fetch TNC ACME configuration when checking renewal: %r', acme_cfg['error']
            )
            return False, None

        renewal_info = fetch_renewal_info(acme_cfg['acme_details']['renewal_info'], cert_id)
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
        within_window: bool = start_time <= current_time
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

    @private
    async def initiate_cert_generation_impl(self) -> dict[str, Any]:
        cert_job = await self.call2(self.s.tn_connect.acme.create_cert)
        await cert_job.wait()
        if cert_job.error:
            raise CallError(cert_job.error)

        return cast(dict[str, Any], cert_job.result)

    @private
    @job(lock='tn_connect_cert_generation')
    async def create_cert(
        self, job: Job, cert_id: int | None = None, cert_renewal_id: str | None = None,
    ) -> dict[str, Any]:
        csr_details: dict[str, str] | None = None
        if cert := (await self.middleware.call('certificate.query', [['id', '=', cert_id]])):
            csr_details = {
                'csr': cert[0]['CSR'],
                'private_key': cert[0]['privatekey'],
            }

        resp = await self.call2(self.s.tn_connect.hostname.register_update_ips, None, True)
        try:
            return cast(dict[str, Any], await create_cert(
                await config_internal(self.context), resp['response'] or {},
                csr_details, cert_renewal_id,
            ))
        except TNCCallError as e:
            raise CallError(str(e))

    @private
    async def revoke_cert(self) -> None:
        tnc_config = await config_internal(self.context)
        if tnc_config['certificate'] is None:
            # If cert generation had failed, there won't be any cert to revoke
            logger.debug('No TNC certificate configured, skipping revocation')
            return

        certificate = await self.middleware.call('certificate.get_instance', tnc_config['certificate'])
        acme_cfg = await self.call2(self.s.tn_connect.acme.config)
        if acme_cfg['error']:
            self.logger.error(
                'Failed to fetch TNC ACME configuration when trying to revoke TNC certificate: %r',
                acme_cfg['error']
            )
            return

        try:
            await self.call2(
                self.s.acme.protocol.revoke_certificate, acme_cfg['acme_details'], certificate['certificate'],
            )
        except CallError:
            logger.error('Failed to revoke TNC certificate', exc_info=True)


async def check_status(middleware: Middleware) -> None:
    if not await middleware.call('failover.is_single_master_node'):
        return

    await middleware.call2(middleware.services.tn_connect.state_check)


async def _event_system_ready(middleware: Middleware, event_type: str, args: dict[str, Any]) -> None:
    if not await middleware.call('system.is_ha_capable'):
        # For HA systems, failover logic will handle this
        await check_status(middleware)
