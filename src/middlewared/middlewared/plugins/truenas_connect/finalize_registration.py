import asyncio
import logging

import jwt
from truenas_connect_utils.status import Status
from truenas_connect_utils.urls import get_registration_finalization_uri

from middlewared.service import job, Service

from .mixin import TNCAPIMixin
from .utils import CLAIM_TOKEN_CACHE_KEY


logger = logging.getLogger('truenas_connect')


class TNCRegistrationFinalizeService(Service, TNCAPIMixin):

    POLLING_GAP_MINUTES = 1

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
                    decoded_token = {}
                    try:
                        decoded_token = jwt.decode(token, options={'verify_signature': False})
                    except jwt.exceptions.DecodeError:
                        logger.error('Invalid JWT token received from TNC')
                        await self.status_update(Status.REGISTRATION_FINALIZATION_FAILED)
                        return
                    else:
                        if diff := {'account_id', 'system_id'} - set(decoded_token):
                            logger.error('JWT token does not contain required fields: %r', diff)
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

            await asyncio.sleep(self.POLLING_GAP_MINUTES * 60)
            config = await self.middleware.call('tn_connect.config')

    async def poll_once(self, claim_token, system_id, tnc_config):
        return await self._call(
            get_registration_finalization_uri(tnc_config), 'post',
            payload={'system_id': system_id, 'claim_token': claim_token},
        )
