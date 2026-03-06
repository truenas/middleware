import asyncio
import datetime
import logging

from truenas_connect_utils.status import Status
from truenas_connect_utils.urls import get_registration_finalization_uri

from middlewared.service import job, Service

from .mixin import TNCAPIMixin
from .utils import calculate_sleep, CLAIM_TOKEN_CACHE_KEY, decode_and_validate_token


logger = logging.getLogger('truenas_connect')


class TNCRegistrationFinalizeService(Service, TNCAPIMixin):

    BACKOFF_BASE_SLEEP = 5

    class Config:
        namespace = 'tn_connect.finalize'
        private = True

    async def status_update(self, status, log_message=None):
        await self.middleware.call('tn_connect.set_status', status.name)
        if log_message:
            logger.error(log_message)

    @job(lock='tnc_finalize_registration')
    async def registration(self, job):
        logger.debug('Starting TNC registration finalization')
        start_time = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        config = await self.middleware.call('tn_connect.config')
        system_id = await self.middleware.call('system.global.id')
        try_num = 1
        while config['status'] == Status.REGISTRATION_FINALIZATION_WAITING.name:
            try:
                claim_token = await self.middleware.call('cache.get', CLAIM_TOKEN_CACHE_KEY)
            except KeyError:
                # We have hit timeout
                # TODO: Add alerts
                logger.debug('TNC claim token has expired')
                await self.status_update(Status.REGISTRATION_FINALIZATION_TIMEOUT)
                return

            try:
                logger.debug('Attempt %r: Polling for TNC registration finalization', try_num)
                status = await self.poll_once(claim_token, system_id, config)
            except asyncio.CancelledError:
                await self.status_update(
                    Status.REGISTRATION_FINALIZATION_TIMEOUT, 'TNC registration finalization polling has been cancelled'
                )
                raise
            except Exception as e:
                logger.debug('TNC registration has not been finalized yet: %r', str(e))
                status = {'error': str(e)}
            finally:
                try_num += 1

            if status['error'] is None:
                # We have got the key now and the registration has been finalized
                if 'token' not in status['response']:
                    logger.error(
                        'Registration finalization failed for TNC as token not found in response: %r',
                        status['response']
                    )
                    await self.status_update(Status.REGISTRATION_FINALIZATION_FAILED)
                else:
                    token = status['response']['token']
                    try:
                        decoded_token = decode_and_validate_token(token)
                    except ValueError as e:
                        logger.error('Failed to validate received token: %s', e)
                        await self.status_update(Status.REGISTRATION_FINALIZATION_FAILED)
                        return

                    await self.middleware.call(
                        'datastore.update', 'truenas_connect', config['id'], {
                            'jwt_token': token,
                            'registration_details': decoded_token,
                        }
                    )
                    await self.status_update(Status.CERT_GENERATION_IN_PROGRESS)
                    logger.debug('TNC registration has been finalized')
                    self.middleware.create_task(self.middleware.call('tn_connect.acme.initiate_cert_generation'))
                    # Remove claim token from cache
                    await self.middleware.call('cache.pop', CLAIM_TOKEN_CACHE_KEY)
                    return
            else:
                logger.debug('TNC registration has not been finalized yet: %r', status['error'])

            sleep_secs = calculate_sleep(start_time, self.BACKOFF_BASE_SLEEP)
            logger.debug('Waiting for %r seconds before attempting to finalize registration', sleep_secs)
            await asyncio.sleep(sleep_secs)
            config = await self.middleware.call('tn_connect.config')

    async def poll_once(self, claim_token, system_id, tnc_config):
        return await self._call(
            get_registration_finalization_uri(tnc_config), 'post',
            payload={'system_id': system_id, 'claim_token': claim_token},
        )
