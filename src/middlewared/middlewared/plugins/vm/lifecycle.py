import asyncio

from middlewared.service import private, Service
from middlewared.utils.asyncio_ import asyncio_map
from middlewared.utils.libvirt.utils import ACTIVE_STATES


SHUTDOWN_LOCK = asyncio.Lock()


class VMService(Service):

    @private
    async def start_on_boot(self):
        for vm in await self.middleware.call('vm.query', [('autostart', '=', True)], {'force_sql_filters': True}):
            try:
                await self.middleware.call('vm.start', vm['id'])
            except Exception as e:
                self.middleware.logger.error(f'Failed to start VM {vm["name"]}: {e}')

    @private
    async def terminate_timeout(self):
        return max(map(lambda v: v['shutdown_timeout'], await self.middleware.call('vm.query')), default=10)

    @private
    async def handle_shutdown(self):
        async def poweroff_stop_vm(vm):
            if vm['status']['state'] == 'RUNNING':
                stop_job = await self.middleware.call('vm.stop', vm['id'], {'force_after_timeout': True})
                await stop_job.wait()
                if stop_job.error:
                    self.middleware.logger.error('Stopping %r VM failed: %r', vm['name'], stop_job.error)
            else:
                try:
                    await self.middleware.call('vm.poweroff', vm['id'])
                except Exception:
                    self.middleware.logger.error('Powering off %r VM failed', vm['name'], exc_info=True)

        vms = await self.middleware.call('vm.query', [('status.state', 'in', ACTIVE_STATES)])
        if vms:
            async with SHUTDOWN_LOCK:  # FIXME: Why a global lock?? Not needed....
                await asyncio_map(poweroff_stop_vm, vms, 16)
                self.middleware.logger.debug('VM(s) stopped successfully')
                # We do this in vm.terminate as well, reasoning for repeating this here is that we don't want to
                # stop libvirt on middlewared restarts, we only want that to happen if a shutdown has been initiated
                # and we have cleanly exited
                await self.middleware.call('vm.deinitialize_vms', {'reload_ui': False})


async def __event_system_ready(middleware, event_type, args):
    # we ignore the 'ready' event on an HA system since the failover event plugin
    # is responsible for starting this service, however, the VMs still need to be
    # initialized (which is what the above callers are doing)
    if await middleware.call('failover.licensed'):
        return

    middleware.create_task(middleware.call('vm.start_on_boot'))


async def __event_system_shutdown(middleware, event_type, args):
    await middleware.call('vm.handle_shutdown')


async def setup(middleware):
    # it's _very_ important that we run this before we do
    # any type of VM initialization. We have to capture the
    # zfs c_max value before we start manipulating these
    # sysctls during vm start/stop
    await middleware.call('sysctl.store_default_arc_max')

    middleware.event_subscribe('system.ready', __event_system_ready)
    middleware.event_subscribe('system.shutdown', __event_system_shutdown)
