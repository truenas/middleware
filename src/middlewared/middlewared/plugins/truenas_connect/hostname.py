import logging

from truenas_connect_utils.exceptions import CallError as TNCCallError
from truenas_connect_utils.hostname import hostname_config, register_update_ips

from middlewared.service import CallError, Service


logger = logging.getLogger('truenas_connect')


class TNCHostnameService(Service):

    class Config:
        namespace = 'tn_connect.hostname'
        private = True

    async def config(self):
        return await hostname_config(await self.middleware.call('tn_connect.config_internal'))

    async def register_update_ips(self, ips=None):
        tnc_config = await self.middleware.call('tn_connect.config_internal')
        # If no IPs provided, use combined IPs from config (direct IPs + interface IPs)
        if ips is None:
            ips = tnc_config['ips'] + tnc_config.get('interfaces_ips', [])
        try:
            return await register_update_ips(tnc_config, ips)
        except TNCCallError as e:
            raise CallError(str(e))
