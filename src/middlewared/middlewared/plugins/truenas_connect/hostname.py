import logging

from truenas_connect_utils.exceptions import CallError as TNCCallError
from truenas_connect_utils.hostname import hostname_config, register_update_ips

from middlewared.service import CallError, Service

from .utils import CONFIGURED_TNC_STATES


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

    async def sync_interface_ips(self):
        logger.debug('Syncing interface IPs for TrueNAS Connect')
        tnc_config = await self.middleware.call('tn_connect.config')
        await self.middleware.call(
            'datastore.update', 'truenas_connect', tnc_config['id'], {
                'interfaces_ips': await self.middleware.call('tn_connect.get_interface_ips'),
            }
        )
        response = await self.middleware.call('tn_connect.hostname.register_update_ips')
        if response['error']:
            logger.error('Failed to update IPs with TrueNAS Connect: %s', response['error'])


async def update_ips(middleware, event_type, args):
    tnc_config = await middleware.call('tn_connect.config')
    if tnc_config['status'] not in CONFIGURED_TNC_STATES or args['fields']['iface'] not in tnc_config['interfaces']:
        # We don't want to do anything if we are not watching for the interface
        # where the IP address change occurred or if TNC is not configured
        return

    logger.info(
        'Updating IPs for TrueNAS Connect due to %s change on interface %s', event_type, args['fields']['iface']
    )
    middleware.create_task(middleware.call('tn_connect.hostname.sync_interface_ips'))


async def setup(middleware):
    middleware.event_subscribe('ipaddress.change', update_ips)
