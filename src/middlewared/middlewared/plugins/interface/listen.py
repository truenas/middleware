from collections import namedtuple
from itertools import zip_longest

from middlewared.api import api_method
from middlewared.api.current import (
    InterfaceListenServicesRestartedOnSyncArgs,
    InterfaceListenServicesRestartedOnSyncResult,
)
from middlewared.service import Service, private

PreparedDelegate = namedtuple("PreparedDelegate", ["delegate", "state", "addresses"])

PRE_SYNC_LISTEN_DELEGATES = []
POST_ROLLBACK_LISTEN_DELEGATES = []


class InterfaceService(Service):

    delegates = []

    class Config:
        namespace_alias = "interfaces"

    @private
    def register_listen_delegate(self, delegate):
        self.delegates.append(delegate)

    @api_method(
        InterfaceListenServicesRestartedOnSyncArgs,
        InterfaceListenServicesRestartedOnSyncResult,
        roles=['NETWORK_INTERFACE_READ']
    )
    async def services_restarted_on_sync(self):
        """
        Returns which services will be set to listen on 0.0.0.0 (and, thus, restarted) on sync.

        Example result:
        [
            // Samba service will be set ot listen on 0.0.0.0 and restarted because it was set up to listen on
            // 192.168.0.1 which is being removed.
            {"type": "SYSTEM_SERVICE", "service": "cifs", "ips": ["192.168.0.1"]},
        ]
        """
        return [dict(await pd.delegate.repr(pd.state), ips=pd.addresses)
                for pd in await self.listen_delegates_prepare()]

    @private
    async def listen_delegates_prepare(self):
        original_datastores = await self.middleware.call("interface.get_original_datastores")
        if not original_datastores:
            return []

        datastores = await self.middleware.call("interface.get_datastores")

        old_addresses = self._collect_addresses(original_datastores)
        addresses = self._collect_addresses(datastores)
        gone_addresses = old_addresses - addresses

        result = []
        for delegate in self.delegates:
            state = await delegate.get_listen_state(gone_addresses)
            delegate_addresses = [address
                                  for address in gone_addresses
                                  if await delegate.listens_on(state, address)]
            if delegate_addresses:
                result.append(PreparedDelegate(delegate, state, delegate_addresses))

        return result

    def _collect_addresses(self, datastores):
        addresses = set()
        for iface, alias in zip_longest(datastores["interfaces"], datastores["alias"], fillvalue={}):
            addresses.add(iface.get("int_address", ""))
            addresses.add(iface.get("int_address_b", ""))
            addresses.add(iface.get("int_vip", ""))
            addresses.add(alias.get("alias_address", ""))
            addresses.add(alias.get("alias_address_b", ""))
            addresses.add(alias.get("alias_vip", ""))
        addresses.discard("")
        return addresses


async def interface_pre_sync(middleware):
    PRE_SYNC_LISTEN_DELEGATES[:] = await middleware.call("interface.listen_delegates_prepare")


async def interface_post_sync(middleware):
    if POST_ROLLBACK_LISTEN_DELEGATES:
        for pd in POST_ROLLBACK_LISTEN_DELEGATES:
            middleware.logger.info("Restoring listen IPs on delegate %r: %r", pd.delegate, pd.state)
            middleware.create_task(pd.delegate.set_listen_state(pd.state))

        POST_ROLLBACK_LISTEN_DELEGATES[:] = []
        return

    for pd in PRE_SYNC_LISTEN_DELEGATES:
        middleware.logger.info("Resetting listen IPs on delegate %r because %r addresses were removed", pd.delegate,
                               pd.addresses)
        middleware.create_task(pd.delegate.reset_listens(pd.state))


async def interface_post_rollback(middleware):
    POST_ROLLBACK_LISTEN_DELEGATES[:] = PRE_SYNC_LISTEN_DELEGATES.copy()


async def setup(middleware):
    middleware.register_hook("interface.pre_sync", interface_pre_sync, sync=True)
    middleware.register_hook("interface.post_sync", interface_post_sync, sync=True)
    middleware.register_hook("interface.post_rollback", interface_post_rollback, sync=True)
