import asyncio
import contextlib
import functools

from middlewared.schema import accepts, Bool, Dict
from middlewared.service import CallError, private, Service
from middlewared.utils import osc, run
from middlewared.utils.asyncio_ import asyncio_map

from .vm_supervisor import VMSupervisorMixin


SHUTDOWN_LOCK = asyncio.Lock()


class VMService(Service, VMSupervisorMixin):

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
    def setup_libvirt_connection(self, timeout=30):
        self.middleware.call_sync(f'vm.initialize_{osc.SYSTEM.lower()}')
        self.middleware.call_sync('vm.wait_for_libvirtd', timeout)

    @private
    async def check_setup_libvirt(self):
        if not await self.middleware.call('service.started', 'libvirtd'):
            await self.middleware.call('vm.setup_libvirt_connection')

    @private
    def initialize_vms(self, timeout=30):
        if self.middleware.call_sync('vm.query'):
            self.setup_libvirt_connection(timeout)
        else:
            return

        # We use datastore.query specifically here to avoid a recursive case where vm.datastore_extend calls
        # status method which in turn needs a vm object to retrieve the libvirt status for the specified VM
        if self._is_connection_alive():
            for vm_data in self.middleware.call_sync('datastore.query', 'vm.vm'):
                vm_data['devices'] = self.middleware.call_sync('vm.device.query', [['vm', '=', vm_data['id']]])
                try:
                    self._add_with_vm_data(vm_data)
                except Exception as e:
                    # Whatever happens, we don't want middlewared not booting
                    self.middleware.logger.error(
                        'Unable to setup %r VM object: %s', vm_data['name'], str(e), exc_info=True
                    )
        else:
            self.middleware.logger.error('Failed to establish libvirt connection')

    @private
    async def initialize_linux(self):
        pass

    @private
    async def initialize_freebsd(self):
        cp = await run(['/sbin/kldstat'], check=False)
        if cp.returncode:
            self.middleware.logger.error('Failed to retrieve kernel modules: %s', cp.stderr.decode())
            return
        else:
            kldstat = cp.stdout.decode()

        for kmod in ('vmm.ko', 'nmdm.ko'):
            if kmod not in kldstat:
                cp = await run(['/sbin/kldload', kmod[:-3]], check=False)
                if cp.returncode:
                    self.middleware.logger.error('Failed to load %r : %s', kmod, cp.stderr.decode())

    @private
    async def start_on_boot(self):
        for vm in await self.middleware.call('vm.query', [('autostart', '=', True)]):
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
