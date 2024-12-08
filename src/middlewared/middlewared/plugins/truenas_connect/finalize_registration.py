import asyncio

import jwt

from middlewared.service import job, Service

from .mixin import TNCAPIMixin
from .status_utils import Status
from .urls import REGISTRATION_FINALIZATION_URI
from .utils import CLAIM_TOKEN_CACHE_KEY


class TNCRegistrationFinalizeService(Service, TNCAPIMixin):

    POLLING_GAP_MINUTES = 3

    class Config:
        namespace = 'tn_connect.finalize'
        private = True

    async def status_update(self, status, log_message=None):
        await self.middleware.call('tn_connect.set_status', status.name)
        if log_message:
            self.logger.error(log_message)

    @job(lock='tnc_finalize_registration')
    async def registration(self, job):
        config = await self.middleware.call('tn_connect.config')
        system_id = await self.middleware.call('system.host_id')
        while config['status'] == Status.REGISTRATION_FINALIZATION_WAITING.name:
            try:
                claim_token = await self.middleware.call('cache.get', CLAIM_TOKEN_CACHE_KEY)
            except KeyError:
                # We have hit timeout
                # TODO: Add alerts
                await self.status_update(Status.REGISTRATION_FINALIZATION_TIMEOUT, 'TNC claim token has expired')
                return

            try:
                status = await self.poll_once(claim_token, system_id)
            except asyncio.CancelledError:
                await self.status_update(
                    Status.REGISTRATION_FINALIZATION_TIMEOUT, 'TNC registration finalization polling has been cancelled'
                )
                raise
            except Exception as e:
                # TODO: We need TNC team to give us something to identify a legit error
                self.logger.error('Failed to finalize registration with TNC', exc_info=True)
                status = {'error': str(e)}

            if status['error'] is None:
                # We have got the key now and the registration has been finalized
                if 'token' not in status['response']:
                    self.logger.error(
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
                        self.logger.error('Invalid JWT token received from TNC')
                        await self.status_update(Status.REGISTRATION_FINALIZATION_FAILED)
                        return
                    else:
                        if diff := {'account_id', 'system_id'} - set(decoded_token):
                            self.logger.error('JWT token does not contain required fields: %r', diff)
                            await self.status_update(Status.REGISTRATION_FINALIZATION_FAILED)
                            return

                    await self.middleware.call(
                        'datastore.update', 'truenas_connect', config['id'], {
                            'jwt_token': token,
                            'registration_details': decoded_token,
                        }
                    )
                    await self.status_update(Status.CERT_GENERATION_IN_PROGRESS)
                    # TODO: Trigger a job to generate certs

            await asyncio.sleep(self.POLLING_GAP_MINUTES * 60)
            config = await self.middleware.call('tn_connect.config')

    async def poll_once(self, claim_token, system_id):
        return await self._call(
            REGISTRATION_FINALIZATION_URI, 'post',
            headers={'Content-Type': 'application/json'},
            payload={'system_id': system_id, 'claim_token': claim_token},
        )
