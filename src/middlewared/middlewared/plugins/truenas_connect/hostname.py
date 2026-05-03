import asyncio
import logging

from truenas_connect_utils.exceptions import CallError as TNCCallError
from truenas_connect_utils.hostname import hostname_config, register_system_config, register_update_ips

from middlewared.service import CallError, Service

from .utils import CONFIGURED_TNC_STATES, TNC_IPS_CACHE_KEY

logger = logging.getLogger('truenas_connect')
_pending_sync = None
_sync_lock = asyncio.Lock()


class TNCHostnameService(Service):

    class Config:
        namespace = 'tn_connect.hostname'
        private = True

    async def basename_from_cert(self):
        config = await self.middleware.call('tn_connect.config')
        if config['enabled'] and config['status'] in CONFIGURED_TNC_STATES and config['certificate']:
            san = await self.middleware.call2(
                self.s.certificate.get_domain_names, config['certificate'],
            )
            return san[0].strip('DNS:') if san else None

    async def config(self):
        return await hostname_config(await self.middleware.call('tn_connect.config_internal'))

    async def register_update_ips(self, ips=None, create_wildcard=False):
        tnc_config = await self.middleware.call('tn_connect.config_internal')
        if ips is None:
            ips = await self.middleware.call('tn_connect.get_effective_ips')

        if await self.middleware.call('system.is_ha_capable'):
            # For HA based systems, we want to ensure that VIP(s) always get added
            ips = (await self.middleware.call('tn_connect.ha_vips')) + ips

        try:
            return await register_update_ips(tnc_config, ips, create_wildcard)
        except TNCCallError as e:
            raise CallError(str(e))

    async def register_system_config(self, websocket_port: int) -> dict:
        """Register system configuration with TrueNAS Connect, including websocket port."""
        tnc_config = await self.middleware.call('tn_connect.config_internal')

        try:
            return await register_system_config(tnc_config, websocket_port)
        except TNCCallError as e:
            raise CallError(str(e))

    async def sync_ips(self, event_details=None):
        if not await self.middleware.call('failover.is_single_master_node'):
            return

        tnc_config = await self.middleware.call('tn_connect.config')

        if tnc_config['status'] not in CONFIGURED_TNC_STATES:
            return

        # When triggered by a network event, only proceed if system.general has
        # wildcards configured for the relevant address family — specific IPs
        # don't change with interface events.
        if event_details:
            general_config = await self.middleware.call('system.general.config')
            has_v4_wildcard = '0.0.0.0' in general_config['ui_address']
            has_v6_wildcard = '::' in general_config['ui_v6address']
            if not has_v4_wildcard and not has_v6_wildcard:
                return

        async with _sync_lock:
            effective_ips = await self.middleware.call('tn_connect.get_effective_ips')

            try:
                cached_ips = await self.middleware.call('cache.get', TNC_IPS_CACHE_KEY)
            except KeyError:
                skip_syncing = False
            else:
                skip_syncing = set(cached_ips) == set(effective_ips)

            if skip_syncing:
                return

            if event_details:
                logger.info(
                    'Updating IPs for TrueNAS Connect due to %s change on interface %s',
                    event_details['type'], event_details['iface'],
                )

            # Skip HTTP call if no IPs available to avoid sending an empty payload.
            # Still cache the empty result to prevent retry storms from repeated netlink events.
            if not effective_ips:
                await self.middleware.call('cache.put', TNC_IPS_CACHE_KEY, effective_ips, 60 * 60)
                return

            logger.debug('Syncing IPs for TrueNAS Connect')
            try:
                await self.middleware.call('tn_connect.hostname.register_update_ips')
            except CallError:
                logger.error('Failed to update IPs with TrueNAS Connect', exc_info=True)
            else:
                await self.middleware.call('cache.put', TNC_IPS_CACHE_KEY, effective_ips, 60 * 60)
                await self.middleware.call_hook('tn_connect.hostname.updated', await self.config())

    async def handle_update_ips(self, event_type, args):
        """
        Handle IP address changes for TrueNAS Connect.
        This method is called when an IP address change event occurs.
        """
        # Skip internal interfaces (docker, veth, tun, tap, etc.) as they are not meant for external connectivity
        internal_interfaces = tuple(await self.middleware.call('interface.internal_interfaces'))
        if args['fields']['iface'].startswith(internal_interfaces):
            return

        try:
            await self.sync_ips({'type': event_type, 'iface': args['fields']['iface']})
        except Exception:
            logger.error('Failed to sync IPs for TrueNAS Connect', exc_info=True)


async def update_ips(middleware, event_type, args):
    global _pending_sync

    iface = args['fields']['iface']
    if iface is None:
        return
    # Docker bridge interfaces use br-<hex_id> naming while user-created
    # bridges use br<digits> (enforced by interface_types.py:35). Filter
    # them out early so they never cancel a pending real-interface sync.
    if iface.startswith('br-'):
        return

    # Debounce rapid netlink events — a single network change (DHCP renewal,
    # Docker start/stop) can fire multiple ipaddress.change events within
    # milliseconds. Cancel any pending sync and reschedule so only one sync
    # fires after the burst settles.
    if _pending_sync is not None:
        _pending_sync.cancel()
    _pending_sync = asyncio.get_event_loop().call_later(
        5,
        lambda: middleware.create_task(
            middleware.call('tn_connect.hostname.handle_update_ips', event_type, args)
        ),
    )


async def on_general_config_update(middleware, *args, **kwargs):
    """Re-sync TNC IPs when system.general UI address settings change.

    We intentionally do not invalidate the TNC IPs cache here. sync_ips()
    compares the freshly resolved effective IPs against the cached set and
    only sends an update to TNC when they actually differ. This avoids
    unnecessary HTTP calls when unrelated system.general fields change
    (timezone, keyboard layout, certificate, etc.).
    """
    try:
        await middleware.call('tn_connect.hostname.sync_ips')
    except Exception:
        logger.error('Failed to sync IPs after system.general update', exc_info=True)


async def setup(middleware):
    middleware.event_subscribe('ipaddress.change', update_ips)
    middleware.register_hook('system.general.post_update', on_general_config_update)
