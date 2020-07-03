import asyncio
import contextlib
import functools

from middlewared.service import CallError, private, Service
from middlewared.utils import osc
from middlewared.utils.asyncio_ import asyncio_map

from .connection import LibvirtConnectionMixin


SHUTDOWN_LOCK = asyncio.Lock()


class VMService(Service, LibvirtConnectionMixin):

    ZFS_ARC_MAX_INITIAL = None

    @private
    async def get_initial_arc_max(self):
        if osc.IS_FREEBSD:
            tunable = await self.middleware.call('tunable.query', [
                ['type', '=', 'SYSCTL'], ['var', '=', 'vfs.zfs.arc.max']
            ])
            if tunable and str(tunable[0]['value']).isdigit():
                return int(tunable[0]['value'])
        return self.ZFS_ARC_MAX_INITIAL

    @private
    async def wait_for_libvirtd(self, timeout):
        async def libvirtd_started(middleware):
            await middleware.call('service.start', 'libvirtd')
            while not await middleware.call('service.started', 'libvirtd'):
                await asyncio.sleep(2)

        try:
            if not await self.middleware.call('service.started', 'libvirtd'):
                await asyncio.wait_for(libvirtd_started(self.middleware), timeout=timeout)
            # We want to do this before initializing libvirt connection
            self._open()
            await self.middleware.call('vm.setup_libvirt_events')
        except (asyncio.TimeoutError, CallError):
            self.middleware.logger.error('Failed to connect to libvirtd')

    @private
    def initialize_vms(self, timeout=10):
        if self.middleware.call_sync('vm.query'):
            self.middleware.call_sync('vm.wait_for_libvirtd', timeout)
        else:
            return

        # We use datastore.query specifically here to avoid a recursive case where vm.datastore_extend calls
        # status method which in turn needs a vm object to retrieve the libvirt status for the specified VM
        if self.LIBVIRT_CONNECTION:
            pass
        else:
            self.middleware.logger.error('Failed to establish libvirt connection')

    @private
    def close_libvirt_connection(self):
        if self.LIBVIRT_CONNECTION:
            with contextlib.suppress(CallError):
                self._close()

    @private
    async def terminate(self):
        async with SHUTDOWN_LOCK:
            await self.middleware.call('vm.close_libvirt_connection')

    @private
    async def terminate_timeout(self):
        return max(map(lambda v: v['shutdown_timeout'], await self.middleware.call('vm.query')), default=10)

    @private
    async def update_zfs_arc_max_initial(self):
        self.ZFS_ARC_MAX_INITIAL = await self.middleware.call('sysctl.get_arc_max')


async def __event_system_ready(middleware, event_type, args):
    """
    Method called when system is ready, supposed to start VMs
    flagged that way.
    """
    async def stop_vm(mw, vm):
        stop_job = await mw.call('vm.stop', vm['id'], {'force_after_timeout': True})
        await stop_job.wait()
        if stop_job.error:
            mw.logger.error(f'Stopping VM {vm["name"]} failed: {stop_job.error}')

    if args['id'] == 'ready':
        await middleware.call('vm.update_zfs_arc_max_initial')

        await middleware.call('vm.initialize_vms')

        if not await middleware.call('system.is_freenas') and await middleware.call('failover.licensed'):
            return

        asyncio.ensure_future(middleware.call('vm.start_on_boot'))
    elif args['id'] == 'shutdown':
        async with SHUTDOWN_LOCK:
            await asyncio_map(
                functools.partial(stop_vm, middleware),
                (await middleware.call('vm.query', [('status.state', '=', 'RUNNING')])), 16
            )
            middleware.logger.debug('VM(s) stopped successfully')
            # We do this in vm.terminate as well, reasoning for repeating this here is that we don't want to
            # stop libvirt on middlewared restarts, we only want that to happen if a shutdown has been initiated
            # and we have cleanly exited
            await middleware.call('vm.close_libvirt_connection')
            await middleware.call('service.stop', 'libvirtd')


async def setup(middleware):
    if await middleware.call('system.ready'):
        asyncio.ensure_future(middleware.call('vm.initialize_vms', 2))  # We use a short timeout here deliberately
    middleware.event_subscribe('system', __event_system_ready)
