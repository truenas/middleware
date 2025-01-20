import logging

from middlewared.service import CallError, Service

from .mixin import TNCAPIMixin
from .urls import get_hostname_url
from .utils import get_account_id_and_system_id


logger = logging.getLogger('truenas_connect')


class TNCHostnameService(Service, TNCAPIMixin):

    class Config:
        namespace = 'tn_connect.hostname'
        private = True

    async def call(self, url, mode, payload=None):
        config = await self.middleware.call('tn_connect.config_internal')
        return await self._call(url, mode, payload=payload, headers=await self.auth_headers(config))

    async def config(self):
        config = await self.middleware.call('tn_connect.config_internal')
        creds = get_account_id_and_system_id(config)
        if not config['enabled'] or creds is None:
            return {
                'error': 'TrueNAS Connect is not enabled or not configured properly',
                'tnc_configured': False,
                'hostname_details': {},
                'base_domain': None,
                'hostname_configured': False,
            }

        resp = (await self.call(get_hostname_url(config).format(**creds), 'get')) | {'base_domain': None}
        resp['hostname_details'] = resp.pop('response')
        for domain in resp['hostname_details']:
            if len(domain.rsplit('.', maxsplit=4)) == 5 and domain.startswith('*.'):
                resp['base_domain'] = domain.split('.', maxsplit=1)[-1]
                break

        return resp | {
            'tnc_configured': True,
            'hostname_configured': bool(resp['hostname_details']),
        }

    async def register_update_ips(self, ips=None):
        tnc_config = await self.middleware.call('tn_connect.config_internal')
        ips = ips or tnc_config['ips']
        logger.debug('Updating TNC hostname configuration with %r ips', ','.join(ips))
        config = await self.config()
        if config['error']:
            raise CallError(f'Failed to fetch TNC hostname configuration: {config["error"]}')

        creds = get_account_id_and_system_id(tnc_config)
        return await self.call(
            get_hostname_url(tnc_config).format(**creds), 'put', payload={'ips': ips},
        )
