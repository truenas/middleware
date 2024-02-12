import asyncio

from middlewared.service import Service, private


class DistributedLockManagerService(Service):
    """
    Support the configuration of the kernel dlm in a multi-controller environment.

    This will handle the following events:
    - kernel udev online lockspace event (aka dlm.join_lockspace)
    - kernel udev offline lockspace event (aka dlm.leave_lockspace)
    - node join event (from another controller)
    - node leave event (from another controller)
    """

    class Config:
        private = True
        namespace = 'dlm'

    resetting = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The nodeID, peernodeID & nodes will be initialized by setup_nodes
        self.nodeID = 0
        self.peernodeID = "Unknown"
        self.nodes = {}
        self.fully_created = False

    @private
    async def setup_nodes(self):
        """
        Setup the self.nodes dict and the self.nodeID.

        It makes no guarantees that the remote node is currently accessible.
        """
        if await self.middleware.call('failover.licensed'):
            # We could determine local by fetching IPs, but failover.node is cheap
            self.node = await self.middleware.call('failover.node')
            self.nodes[1] = {'ip': '169.254.10.1', 'local': self.node == 'A'}
            self.nodes[2] = {'ip': '169.254.10.2', 'local': self.node == 'B'}

        for nodeid, node in self.nodes.items():
            if node['local']:
                self.nodeID = nodeid
            else:
                self.peernodeID = nodeid

    @private
    async def node_ready(self):
        if not self.nodeID:
            await self.middleware.call('dlm.create')
        return await self.middleware.call('dlm.kernel.comms_node_ready', self.nodeID)

    @private
    async def create(self):
        if self.fully_created:
            return
        if not self.nodes:
            await self.middleware.call('dlm.setup_nodes')

        # For code robustness sake, ensure the dlm is loaded.  Should not be necessary.
        await self.middleware.call('dlm.kernel.load_kernel_module')

        # Setup the kernel dlm static config (i.e. define nodes, but not lockspaces)
        for nodeid, node in self.nodes.items():
            if node['local']:
                await self.middleware.call('dlm.kernel.comms_add_node', nodeid, node['ip'], node['local'])
            elif await self.middleware.call('failover.remote_connected'):
                await self.middleware.call('dlm.kernel.comms_add_node', nodeid, node['ip'], node['local'])
                self.fully_created = True

    @private
    async def lockspace_member(self, dest_nodeid, lockspace_name):
        await self.middleware.call('dlm.create')
        if dest_nodeid == self.nodeID:
            # Local operation
            self.logger.debug('[LOCAL] Checking whether lockspace %s exists on node %d', lockspace_name, dest_nodeid)

            if await self.middleware.call('dlm.kernel.lockspace_present', lockspace_name):
                return (dest_nodeid, True)

        elif await self.middleware.call('failover.remote_connected'):
            # Remote operation
            self.logger.debug('[REMOTE] Checking whether lockspace %s exists on node %d', lockspace_name, dest_nodeid)
            return await self.middleware.call(
                'failover.call_remote', 'dlm.lockspace_member', [dest_nodeid, lockspace_name], {'timeout': 5}
            )
        return (dest_nodeid, False)

    @private
    async def lockspace_members(self, lockspace_name):
        await self.middleware.call('dlm.create')
        result = set()
        exceptions = await asyncio.gather(*[self.lockspace_member(nodeid, lockspace_name) for nodeid in self.nodes], return_exceptions=True)
        for exc in exceptions:
            if isinstance(exc, Exception):
                self.logger.warning(exc)
            else:
                (nodeid, member) = exc
                if nodeid and member:
                    result.add(nodeid)
        return list(result)

    @private
    async def stop_kernel_lockspace(self, dest_nodeid, lockspace_name):
        if dest_nodeid == self.nodeID:
            # Local operation
            self.logger.debug('[LOCAL] Stopping kernel lockspace %s on node %d', lockspace_name, dest_nodeid)
            await self.middleware.call('dlm.kernel.lockspace_stop', lockspace_name)
        elif await self.middleware.call('failover.remote_connected'):
            # Remote operation
            self.logger.debug('[REMOTE] Stopping kernel lockspace %s on node %d', lockspace_name, dest_nodeid)
            await self.middleware.call(
                'failover.call_remote', 'dlm.stop_kernel_lockspace', [dest_nodeid, lockspace_name], {'timeout': 5}
            )

    @private
    async def start_kernel_lockspace(self, dest_nodeid, lockspace_name):
        if dest_nodeid == self.nodeID:
            # Local operation
            self.logger.debug('[LOCAL] Starting kernel lockspace %s on node %d', lockspace_name, dest_nodeid)

            # If already stopped, tell the kernel lockspace to start
            await self.middleware.call('dlm.kernel.lockspace_start', lockspace_name)

        elif await self.middleware.call('failover.remote_connected'):
            # Remote operation
            self.logger.debug('[REMOTE] Starting kernel lockspace %s on node %d', lockspace_name, dest_nodeid)
            await self.middleware.call(
                'failover.call_remote', 'dlm.start_kernel_lockspace', [dest_nodeid, lockspace_name], {'timeout': 5}
            )

    @private
    async def join_kernel_lockspace(self, dest_nodeid, lockspace_name, joining_nodeid, nodeIDs):
        if dest_nodeid == self.nodeID:
            # Local operation
            self.logger.debug('[LOCAL] Joining kernel lockspace %s for node %s on node %s', lockspace_name, joining_nodeid, dest_nodeid)

            # Ensure kernel lockspace is stopped
            if not await self.middleware.call('dlm.kernel.lockspace_is_stopped', lockspace_name):
                self.logger.warning('Lockspace %s not stopped', lockspace_name)
                return

            # If joining set global id_
            if dest_nodeid == joining_nodeid:
                await self.middleware.call('dlm.kernel.lockspace_set_global_id', lockspace_name)
                for nodeid in nodeIDs:
                    await self.middleware.call('dlm.kernel.lockspace_add_node', lockspace_name, nodeid)
            else:
                # Add the joining node
                await self.middleware.call('dlm.kernel.lockspace_add_node', lockspace_name, joining_nodeid)

            # Start kernel lockspace again.
            await self.middleware.call('dlm.kernel.lockspace_start', lockspace_name)

            # If joining set event_done 0
            if dest_nodeid == joining_nodeid:
                await self.middleware.call('dlm.kernel.set_sysfs_event_done', lockspace_name, 0)

        elif await self.middleware.call('failover.remote_connected'):
            # Remote operation
            self.logger.debug('[REMOTE] Joining kernel lockspace %s for node %s on node %s', lockspace_name, joining_nodeid, dest_nodeid)
            await self.middleware.call(
                'failover.call_remote', 'dlm.join_kernel_lockspace', [dest_nodeid, lockspace_name, joining_nodeid, nodeIDs], {'timeout': 5}
            )

    @private
    async def leave_kernel_lockspace(self, dest_nodeid, lockspace_name, leaving_nodeid):
        if dest_nodeid == self.nodeID:
            # Local operation
            self.logger.debug('[LOCAL] Node %s leaving kernel lockspace %s', leaving_nodeid, lockspace_name)

            # Are we the ones leaving?
            if dest_nodeid == leaving_nodeid:
                # Remove members
                await self.middleware.call('dlm.kernel.lockspace_leave', lockspace_name)
                # Event done
                await self.middleware.call('dlm.kernel.set_sysfs_event_done', lockspace_name, 0)
                return

            # Make config changes
            await self.middleware.call('dlm.kernel.lockspace_remove_node', lockspace_name, leaving_nodeid)

        elif await self.middleware.call('failover.remote_connected'):
            # Remote operation
            self.logger.debug('[REMOTE] Node %s leaving kernel lockspace %s on %s', leaving_nodeid, lockspace_name, dest_nodeid)
            await self.middleware.call(
                'failover.call_remote', 'dlm.leave_kernel_lockspace', [dest_nodeid, lockspace_name, leaving_nodeid], {'timeout': 5}
            )

    @private
    async def join_lockspace(self, lockspace_name):
        self.logger.info('Joining lockspace %s', lockspace_name)
        await self.middleware.call('dlm.create')
        try:
            # Note that by virtue of this being a join_lockspace kernel lockspace stopped is already True (on this node)
            await self.middleware.call('dlm.kernel.lockspace_mark_stopped', lockspace_name)

            nodeIDs = set(await self.middleware.call('dlm.lockspace_members', lockspace_name))

            # Stop kernel lockspace (on all other nodes)
            await asyncio.gather(*[self.stop_kernel_lockspace(nodeid, lockspace_name) for nodeid in nodeIDs])

            nodeIDs.add(self.nodeID)
            # Join the kernel lockspace (on all nodes)
            await asyncio.gather(*[self.join_kernel_lockspace(nodeid, lockspace_name, self.nodeID, list(nodeIDs)) for nodeid in nodeIDs])
        except Exception:
            self.logger.error('Failed to join lockspace %s', lockspace_name, exc_info=True)
            await self.middleware.call('dlm.kernel.set_sysfs_event_done', lockspace_name, 1)

    @private
    async def leave_lockspace(self, lockspace_name):
        self.logger.info('Leaving lockspace %s', lockspace_name)
        await self.middleware.call('dlm.create')
        if DistributedLockManagerService.resetting:
            await self.middleware.call('dlm.kernel.lockspace_stop', lockspace_name)
            await self.middleware.call('dlm.kernel.lockspace_leave', lockspace_name)
            await self.middleware.call('dlm.kernel.set_sysfs_event_done', lockspace_name, 0)
            return
        try:

            nodeIDs = set(await self.middleware.call('dlm.lockspace_members', lockspace_name))

            # Stop kernel lockspace (on all nodes)
            await asyncio.gather(*[self.stop_kernel_lockspace(nodeid, lockspace_name) for nodeid in nodeIDs])

            # Leave the kernel lockspace (on all nodes).
            await asyncio.gather(*[self.leave_kernel_lockspace(nodeid, lockspace_name, self.nodeID) for nodeid in nodeIDs])

            nodeIDs.remove(self.nodeID)
            # Start the kernel lockspace on remaining nodes
            await asyncio.gather(*[self.start_kernel_lockspace(nodeid, lockspace_name) for nodeid in nodeIDs])

        except Exception:
            self.logger.error('Failed to leave lockspace %s', lockspace_name, exc_info=True)
            await self.middleware.call('dlm.kernel.lockspace_start', lockspace_name)
            await self.middleware.call('dlm.kernel.set_sysfs_event_done', lockspace_name, 1)

    @private
    async def add_node(self, nodeid):
        """
        Possible future enhancement.

        Handle addition of a node.
        """
        raise NotImplementedError("add_node not currently implemented")
        # if await self.middleware.call('failover.remote_connected'):
        node = self.nodes.get(nodeid)
        if node:
            await self.middleware.call('dlm.kernel.comms_add_node', nodeid, node['ip'], node['local'])

    @private
    async def remove_node(self, nodeid):
        """
        Possible future enhancement.

        Handle a node failure.
        """
        raise NotImplementedError("remove_node not currently implemented")
        node = self.nodes.get(nodeid)
        if node:
            # Remove the node from any lockspaces it is in
            for lockspace_name in await self.middleware.call('dlm.kernel.node_lockspaces', nodeid):
                # Anticipate the day when we have N nodes, but for now this equates to this node.
                nodeIDs = set(await self.middleware.call('dlm.lockspace_members', lockspace_name))
                nodeIDs.remove(nodeid)
                await asyncio.gather(*[self.stop_kernel_lockspace(node_id, lockspace_name) for node_id in nodeIDs])
                await asyncio.gather(*[self.leave_kernel_lockspace(node_id, lockspace_name, nodeid) for node_id in nodeIDs])
                await asyncio.gather(*[self.start_kernel_lockspace(node_id, lockspace_name) for node_id in nodeIDs])

            # await self.middleware.call('dlm.kernel.comms_remove_node', nodeid)

    @private
    async def remote_down(self):
        """
        Handle a node HA remote node going down.
        """
        self.logger.info('Remote node %s down', self.peernodeID)

    @private
    async def local_remove_peer(self, lockspace_name):
        """Remove the peer node from the specified lockspace without communicating with it."""
        await self.middleware.call('dlm.kernel.lockspace_stop', lockspace_name)
        await self.middleware.call('dlm.kernel.lockspace_remove_node', lockspace_name, self.peernodeID)
        await self.middleware.call('dlm.kernel.lockspace_start', lockspace_name)

    @private
    async def lockspaces(self):
        """Return a list of lockspaces to which we are currently joined."""
        await self.middleware.call('dlm.create')
        return list(await self.middleware.call('dlm.kernel.node_lockspaces', self.nodeID))

    @private
    async def peer_lockspaces(self):
        """Return a list of lockspaces to which we are currently joined, and which also
        contain the PEER node"""
        await self.middleware.call('dlm.create')
        return list(await self.middleware.call('dlm.kernel.node_lockspaces', self.peernodeID))

    @private
    async def eject_peer(self):
        """Locally remove the PEER node from all of the lockspaces to which we are both joined."""
        await self.middleware.call('dlm.create')
        lockspace_names = await self.middleware.call('dlm.peer_lockspaces')
        if lockspace_names:
            self.logger.info('Ejecting peer from %d lockspaces', len(lockspace_names))
            await asyncio.gather(*[self.local_remove_peer(lockspace_name) for lockspace_name in lockspace_names])

    @private
    async def local_reset(self, disable_iscsi=True):
        """Locally remove the PEER node from all lockspaces and reset cluster_mode to
        zero, WITHOUT talking to the peer node."""
        # First turn off all access to targets from outside.
        if disable_iscsi:
            await self.middleware.call('iscsi.scst.disable')

        # Locally eject the peer.  Will prevent remote comms below.
        await self.eject_peer()

        # Finally turn off cluster mode locally on all extents
        try:
            DistributedLockManagerService.resetting = True
            await self.middleware.call('iscsi.scst.set_all_cluster_mode', 0)
        finally:
            DistributedLockManagerService.resetting = False


async def udev_dlm_hook(middleware, data):
    """
    This hook is called on udevd dlm type events.  It's purpose is to
    allow configuration of dlm lockspaces by handling 'online' and
    'offline' events.

    At the moment this should only be used in HA systems with ALUA enabled
    for iSCSI targets, but there are aspects that are generic and can
    be implemented even if this was not the configuration.
    """
    if data.get('SUBSYSTEM') != 'dlm' or data.get('ACTION') not in ['online', 'offline']:
        return

    lockspace = data.get('LOCKSPACE')
    if lockspace is None:
        middleware.logger.error('Missing lockspace name', exc_info=True)
        return

    if data['ACTION'] == 'online':
        await middleware.call('dlm.join_lockspace', lockspace)
    elif data['ACTION'] == 'offline':
        await middleware.call('dlm.leave_lockspace', lockspace)


def remote_down_event(middleware, *args, **kwargs):
    middleware.call_sync('dlm.remote_down')


async def setup(middleware):
    middleware.register_hook('udev.dlm', udev_dlm_hook)
    # Comment out placeholder call for possible future enhancement.
    # await middleware.call('failover.remote_on_connect', remote_status_event)
    # await middleware.call('failover.remote_on_disconnect', remote_down_event)
