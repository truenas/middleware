import logging

from truenas_connect_utils.config import get_account_id_and_system_id
from truenas_connect_utils.hostname import hostname_config
from truenas_connect_utils.urls import get_hostname_url

from middlewared.service import CallError, Service

from .mixin import TNCAPIMixin


logger = logging.getLogger('truenas_connect')


class TNCHostnameService(Service, TNCAPIMixin):

    class Config:
        namespace = 'tn_connect.hostname'
        private = True

    async def call(self, url, mode, payload=None):
        config = await self.middleware.call('tn_connect.config_internal')
        return await self._call(url, mode, payload=payload, headers=await self.auth_headers(config))

    async def config(self):
        return await hostname_config(await self.middleware.call('tn_connect.config_internal'))

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
