import asyncio

from middlewared.service import job, Service

from .mixin import TNCAPIMixin
from .urls import REGISTRATION_FINALIZATION_URI


class TNCRegistrationFinalizeService(Service, TNCAPIMixin):

    POLLING_GAP_MINUTES = 5

    class Config:
        namespace = 'tn_connect.finalize'
        private = True

    @job(lock='tnc_finalize_registration')
    async def registration(self, job):
        config = await self.middleware.call('tn_connect.config')
        while config['enabled']:
            try:
                status = await self.poll_once(config)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                # TODO: Add status management here
                self.logger.error('Failed to finalize registration with TNC', exc_info=True)
                status = {'error': str(e)}

            if status['error'] is None:
                # We have got the key now and the registration has been finalized
                if 'token' not in status['response']:
                    self.logger.error(
                        'Registration finalization failed for TNC as token not found in response: %r',
                        status['response']
                    )
                else:
                    token = status['response']['token']
                    await self.middleware.call(
                        'datastore.update', 'truenas_connect', config['id'], {
                            'jwt_token': token,
                            'jwt_token_system_id': config['claim_token_system_id'],  # FIXME: Sanity check
                            'claim_token': None,
                            'claim_token_system_id': None,
                        }
                    )

            await asyncio.sleep(self.POLLING_GAP_MINUTES * 60)
            config = await self.middleware.call('tn_connect.config')

    async def poll_once(self, config):
        return await self._call(
            REGISTRATION_FINALIZATION_URI, 'post',
            headers={'Content-Type': 'application/json'},
            payload={'system_id': config['claim_token_system_id'], 'claim_token': config['claim_token']},
        )
