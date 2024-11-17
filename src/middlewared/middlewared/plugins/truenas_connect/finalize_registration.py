from middlewared.service import job, Service

from .mixin import TNCAPIMixin


class TNCRegistrationFinalizeService(Service, TNCAPIMixin):

    POLLING_GAP_MINUTES = 5

    class Config:
        namespace = 'tn_connect.finalize'
        private = True

    @job(lock='tnc_finalize_registration')
    async def registration(self, job):
        config = await self.middleware.call('tn_connect.config')
        while config['enabled']:
            pass

    async def poll_once(self, config):
        pass
