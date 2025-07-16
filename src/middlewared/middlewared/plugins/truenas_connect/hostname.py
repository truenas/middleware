import asyncio
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

        # Get interface IPs based on use_all_interfaces flag
        if tnc_config['use_all_interfaces']:
            interfaces_ips = await self.middleware.call('tn_connect.get_all_interface_ips')
        else:
            interfaces_ips = await self.middleware.call('tn_connect.get_interface_ips', tnc_config['interfaces'])

        logger.debug('Updating TrueNAS Connect with interface IPs: %r', ', '.join(interfaces_ips))
        await self.middleware.call(
            'datastore.update', 'truenas_connect', tnc_config['id'], {
                'interfaces_ips': interfaces_ips,
            }
        )
        response = await self.middleware.call('tn_connect.hostname.register_update_ips')
        if response['error']:
            logger.error('Failed to update IPs with TrueNAS Connect: %s', response['error'])

    async def handle_update_ips(self, event_type, args):
        """
        Handle IP address changes for TrueNAS Connect.
        This method is called when an IP address change event occurs.
        """
        tnc_config = await self.middleware.call('tn_connect.config')

        # Skip if interface is None (can happen in some edge cases)
        if args['fields']['iface'] is None:
            return

        # Skip if TrueNAS Connect is not properly configured
        if tnc_config['status'] not in CONFIGURED_TNC_STATES:
            return

        # Skip if we're not monitoring all interfaces and this interface is not in our watch list
        if tnc_config['use_all_interfaces'] is False and args['fields']['iface'] not in tnc_config['interfaces']:
            return

        # Skip internal interfaces (docker, veth, tun, tap, etc.) as they are not meant for external connectivity
        internal_interfaces = tuple(await self.middleware.call('interface.internal_interfaces'))
        if args['fields']['iface'].startswith(internal_interfaces):
            return

        logger.info(
            'Updating IPs for TrueNAS Connect due to %s change on interface %s', event_type, args['fields']['iface']
        )
        await self.sync_interface_ips()


async def update_ips(middleware, event_type, args):
    # We want to call the handle ips method after a 5 second delay because what happens when an app is started
    # or stopped is that the IP address change event is triggered before docker actually registers the new interface
    # it created which means we are not successfully able to isolate the docker interface as an internal interface
    # This helps us save on an unnecessary IP sync with TNC
    asyncio.get_event_loop().call_later(
        5,
        lambda: middleware.create_task(
            middleware.call('tn_connect.hostname.handle_update_ips', event_type, args)
        ),
    )


async def setup(middleware):
    middleware.event_subscribe('ipaddress.change', update_ips)
