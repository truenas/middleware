from middlewared.service import Service

from .acme_utils import normalize_acme_config
from .mixin import TNCAPIMixin
from .urls import ACME_CONFIG_URL
from .utils import get_account_id_and_system_id


class TNCACMEService(Service, TNCAPIMixin):

    class Config:
        private = True
        namespace = 'tn_connect.acme'

    async def call(self, url, mode, payload=None):
        config = await self.middleware.call('tn_connect.config')
        return await self._call(url, mode, payload=payload, headers=await self.auth_headers(config))

    async def config(self):
        config = await self.middleware.call('tn_connect.config')
        creds = get_account_id_and_system_id(config)
        if not config['enabled'] or creds is None:
            return {
                'error': 'TrueNAS Connect is not enabled or not configured properly',
                'tnc_configured': False,
                'acme_details': {},
            }

        resp = await self.call(ACME_CONFIG_URL.format(account_id=creds['account_id']), 'get')
        resp['acme_details'] = resp.pop('response')
        resp = normalize_acme_config(resp)
        return resp | {
            'tnc_configured': True,
        }
