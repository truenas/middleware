from middlewared.service import Service

from .mixin import TNCAPIMixin
from .urls import HOSTNAME_URL
from .utils import get_account_id_and_system_id


class TNCHostnameService(Service, TNCAPIMixin):

    class Config:
        namespace = 'tn_connect.hostname'
        private = True

    async def call(self, mode, payload=None):
        config = await self.middleware.call('tn_connect.config')
        creds = get_account_id_and_system_id(config)
        return await self._call(
            HOSTNAME_URL.format(**creds), mode, payload=payload, headers=await self.auth_headers(config)
        )

    async def query(self, filters, options):
        config = await self.middleware.call('tn_connect.config')
        creds = get_account_id_and_system_id(config)
        if not config['enabled'] or creds is None:
            return []

        return await self.call('get')
