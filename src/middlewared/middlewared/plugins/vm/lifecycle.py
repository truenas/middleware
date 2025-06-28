import asyncio
import contextlib

from middlewared.service import CallError, private, Service
from middlewared.utils.asyncio_ import asyncio_map

from .utils import ACTIVE_STATES
from .vm_supervisor import VMSupervisorMixin


SHUTDOWN_LOCK = asyncio.Lock()


class VMService(Service, VMSupervisorMixin):

    @private
    async def wait_for_libvirtd(self, timeout):
        async def libvirtd_started(middleware):
            await middleware.call('service.start', 'libvirtd')
            while not await middleware.call('service.started', 'libvirtd'):
                await asyncio.sleep(2)

        try:
            self._system_supports_virtualization()
            if not await self.middleware.call('service.started', 'libvirtd'):
                await asyncio.wait_for(self.middleware.create_task(libvirtd_started(self.middleware)), timeout=timeout)
            # We want to do this before initializing libvirt connection
            await self.middleware.run_in_thread(self._open)
            await self.middleware.run_in_thread(self._check_connection_alive)
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
            self.middleware.call_sync('service.reload', 'http')
        else:
            self.middleware.logger.error('Failed to establish libvirt connection')

    @private
    async def start_on_boot(self):
        # FIXME: Remove this endpoint
        pass

    @private
    async def deinitialize_vms(self, options):
        await self.middleware.call('vm.close_libvirt_connection')
        if options.get('reload_ui'):
            await self.middleware.call('service.reload', 'http')
        if options.get('stop_libvirt'):
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
            'libvirt_domains': self._list_domains() if self.LIBVIRT_CONNECTION else None,
        }

    @private
    async def terminate(self):
        async with SHUTDOWN_LOCK:
            await self.middleware.call('vm.close_libvirt_connection')

    @private
    async def terminate_timeout(self):
        return max(map(lambda v: v['shutdown_timeout'], await self.middleware.call('vm.query')), default=10)


async def __event_system_ready(middleware, event_type, args):
    """
    Method called when system is ready, supposed to start VMs
    flagged that way.
    """
    await middleware.call('vm.initialize_vms')

    # we ignore the 'ready' event on an HA system since the failover event plugin
    # is responsible for starting this service, however, the VMs still need to be
    # initialized (which is what the above callers are doing)
    if await middleware.call('failover.licensed'):
        return

    middleware.create_task(middleware.call('vm.start_on_boot'))


async def __event_system_shutdown(middleware, event_type, args):
    async def poweroff_stop_vm(vm):
        if vm['status']['state'] == 'RUNNING':
            stop_job = await middleware.call('vm.stop', vm['id'], {'force_after_timeout': True})
            await stop_job.wait()
            if stop_job.error:
                middleware.logger.error('Stopping %r VM failed: %r', vm['name'], stop_job.error)
        else:
            try:
                await middleware.call('vm.poweroff', vm['id'])
            except Exception:
                middleware.logger.error('Powering off %r VM failed', vm['name'], exc_info=True)

    vms = await middleware.call('vm.query', [('status.state', 'in', ACTIVE_STATES)])
    if vms:
        async with SHUTDOWN_LOCK:  # FIXME: Why a global lock?? Not needed....
            await asyncio_map(poweroff_stop_vm, vms, 16)
            middleware.logger.debug('VM(s) stopped successfully')
            # We do this in vm.terminate as well, reasoning for repeating this here is that we don't want to
            # stop libvirt on middlewared restarts, we only want that to happen if a shutdown has been initiated
            # and we have cleanly exited
            await middleware.call('vm.deinitialize_vms', {'reload_ui': False})


async def setup(middleware):
    # it's _very_ important that we run this before we do
    # any type of VM initialization. We have to capture the
    # zfs c_max value before we start manipulating these
    # sysctls during vm start/stop
    await middleware.call('sysctl.store_default_arc_max')

    if await middleware.call('system.ready'):
        middleware.create_task(middleware.call('vm.initialize_vms', 5))  # We use a short timeout here deliberately
    middleware.event_subscribe('system.ready', __event_system_ready)
    middleware.event_subscribe('system.shutdown', __event_system_shutdown)
