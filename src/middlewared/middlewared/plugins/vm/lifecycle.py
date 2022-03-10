import asyncio
import contextlib
import functools

from middlewared.schema import accepts, Bool, Dict
from middlewared.service import CallError, private, Service
from middlewared.utils.asyncio_ import asyncio_map

from .vm_supervisor import VMSupervisorMixin


SHUTDOWN_LOCK = asyncio.Lock()


class VMService(Service, VMSupervisorMixin):

    ZFS_ARC_MAX_INITIAL = None

    @private
    async def get_initial_arc_max(self):
        return self.ZFS_ARC_MAX_INITIAL

    @private
    async def wait_for_libvirtd(self, timeout):
        async def libvirtd_started(middleware):
            await middleware.call('service.start', 'libvirtd')
            while not await middleware.call('service.started', 'libvirtd'):
                await asyncio.sleep(2)

        try:
            self._system_supports_virtualization()
            if not await self.middleware.call('service.started', 'libvirtd'):
                await asyncio.wait_for(libvirtd_started(self.middleware), timeout=timeout)
            # We want to do this before initializing libvirt connection
            self._open()
            self._check_connection_alive()
            await self.middleware.call('vm.setup_libvirt_events')
        except (asyncio.TimeoutError, CallError):
            self.middleware.logger.error('Failed to setup libvirt', exc_info=True)

    @private
    def setup_libvirt_connection(self, timeout=30):
        self.middleware.call_sync('vm.wait_for_libvirtd', timeout)

    @private
    async def check_setup_libvirt(self):
        if not await self.middleware.call('service.started', 'libvirtd'):
            await self.middleware.call('vm.setup_libvirt_connection')

    @private
    def initialize_vms(self, timeout=30):
        vms = self.middleware.call_sync('vm.query')
        if vms and self._is_kvm_supported():
            self.setup_libvirt_connection(timeout)
        else:
            return

        if self._is_connection_alive():
            for vm_data in vms:
                try:
                    self._add_with_vm_data(vm_data)
                except Exception as e:
                    # Whatever happens, we don't want middlewared not booting
                    self.middleware.logger.error(
                        'Unable to setup %r VM object: %s', vm_data['name'], str(e), exc_info=True
                    )
            self.middleware.call_sync('service.reload', 'haproxy')
        else:
            self.middleware.logger.error('Failed to establish libvirt connection')

    @private
    async def start_on_boot(self):
        for vm in await self.middleware.call('vm.query', [('autostart', '=', True)], {'force_sql_filters': True}):
            try:
                await self.middleware.call('vm.start', vm['id'])
            except Exception as e:
                self.middleware.logger.error(f'Failed to start VM {vm["name"]}: {e}')

    @private
    @accepts(
        Dict(
            'deinitialize_vms_options',
            Bool('stop_libvirt', default=True),
        )
    )
    async def deinitialize_vms(self, options):
        await self.middleware.call('vm.close_libvirt_connection')
        await self.middleware.call('service.stop', 'haproxy')
        if options['stop_libvirt']:
            await self.middleware.call('service.stop', 'libvirtd')

    @private
    def close_libvirt_connection(self):
        if self.LIBVIRT_CONNECTION:
            with contextlib.suppress(CallError):
                self._close()

    @private
    def setup_details(self):
        return {
            'connected': self._is_connection_alive(),
            'connection_initialised': bool(self.LIBVIRT_CONNECTION),
            'domains': list(self.vms.keys()),
        }

    @private
    async def terminate(self):
        async with SHUTDOWN_LOCK:
            await self.middleware.call('vm.deinitialize_vms', {'stop_libvirt': False})

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

        # we ignore the 'ready' event on an HA system since the failover event plugin
        # is responsible for starting this service, however, the VMs still need to be
        # initialized (which is what the above callers are doing)
        if await middleware.call('failover.licensed'):
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
            await middleware.call('vm.deinitialize_vms')


async def setup(middleware):
    await middleware.call('vm.update_zfs_arc_max_initial')
    if await middleware.call('system.ready'):
        asyncio.ensure_future(middleware.call('vm.initialize_vms', 5))  # We use a short timeout here deliberately
    middleware.event_subscribe('system', __event_system_ready)
