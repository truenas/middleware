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

    async def config(self):
        config = await self.middleware.call('tn_connect.config')
        creds = get_account_id_and_system_id(config)
        if not config['enabled'] or creds is None:
            return {
                'error': 'TrueNAS Connect is not enabled or not configured properly',
                'tnc_configured': False,
                'hostname_details': {},
                'base_domain': None,
                'hostname_configured': False,
            }

        resp = await self.call('get')
        resp['hostname_details'] = resp.pop('response') | {'base_domain': None}
        for domain in resp['hostname_details']:
            if len(domain.rsplit('.', maxsplit=4)) == 4:
                resp['base_domain'] = domain
                break

        return resp | {
            'tnc_configured': True,
            'hostname_configured': bool(resp['hostname_details']),
        }

    async def register_update_ips(self, payload):
        return await self.call('post', payload=payload)
