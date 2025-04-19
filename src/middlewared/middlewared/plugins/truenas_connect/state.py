import logging

from truenas_connect_utils.status import Status

from middlewared.service import Service


logger = logging.getLogger('truenas_connect')


class TrueNASConnectStateService(Service):

    class Config:
        namespace = 'tn_connect.state'
        private = True

    async def handle_registration_finalization_waiting_state(self):
        tn_config = await self.middleware.call('tn_connect.config')
        if tn_config['status'] == Status.REGISTRATION_FINALIZATION_WAITING.name:
            logger.debug(
                'Registration finalization failed as middleware was restarted while waiting '
                'for TNC registration finalization'
            )
            # This means middleware got restarted or the system was rebooted while we were waiting for
            # registration to finalize, so in this case we set the state to registration failed
            await self.middleware.call('tn_connect.finalize.status_update', Status.REGISTRATION_FINALIZATION_FAILED)
