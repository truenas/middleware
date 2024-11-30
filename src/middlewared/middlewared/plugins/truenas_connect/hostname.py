from middlewared.service import CallError, Service

from .mixin import TNCAPIMixin
from .urls import HOSTNAME_URL, LECA_HOSTNAME_URL
from .utils import get_account_id_and_system_id


class TNCHostnameService(Service, TNCAPIMixin):

    class Config:
        namespace = 'tn_connect.hostname'
        private = True

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
                'hostname_details': {},
                'base_domain': None,
                'hostname_configured': False,
            }

        resp = (await self.call(HOSTNAME_URL.format(**creds), 'get')) | {'base_domain': None}
        resp['hostname_details'] = resp.pop('response')
        for domain in resp['hostname_details']:
            if len(domain.rsplit('.', maxsplit=4)) == 4:
                resp['base_domain'] = domain
                break

        return resp | {
            'tnc_configured': True,
            'hostname_configured': bool(resp['hostname_details']),
        }

    async def register_update_ips(self):
        tnc_config = await self.middleware.call('tn_connect.config')
        config = await self.config()
        if config['error']:
            raise CallError(f'Failed to fetch TNC hostname configuration: {config["error"]}')

        register = config['hostname_configured'] is False
        if register:
            payload = {
                'ips': [tnc_config['ip']],
                'system_id': tnc_config['jwt_details']['system_id'],
                'create_wildcard': True,
            }
        else:
            payload = {config['base_domain']: tnc_config['ip']}

        # FIXME: Put does not give json in response, handle that and is broken upstream atm as well
        return await self.call(
            LECA_HOSTNAME_URL, 'post' if register else 'put', payload=payload,
        )
