from middlewared.service import Service

from .mixin import TNCAPIMixin
from .utils import get_account_id_and_system_id


class TNCHeartbeatService(Service, TNCAPIMixin):

    class Config:
        namespace = 'tn_connect.heartbeat'
        private = True

    async def call(self, url, mode, payload=None):
        config = await self.middleware.call('tn_connect.config_internal')
        return await self._call(url, mode, payload=payload, headers=await self.auth_headers(config))

    async def start(self):
        tnc_config = await self.middleware.call('tn_connect.config_internal')
