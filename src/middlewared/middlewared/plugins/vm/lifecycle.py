import asyncio

from middlewared.service import private, Service
from middlewared.utils.libvirt.utils import ACTIVE_STATES


async def _stop_one_vm(middleware, vm):
    try:
        if vm['status']['state'] == 'RUNNING':
            job = await middleware.call('vm.stop', vm['id'], {'force_after_timeout': True})
            await job.wait(raise_error=True)
        else:
            await middleware.call('vm.poweroff', vm['id'])
    except Exception:
        middleware.logger.error('Failed to stop %r VM', vm['name'], exc_info=True)


class VMService(Service):

    @private
    async def start_on_boot(self):
        for vm in await self.middleware.call('vm.query', [('autostart', '=', True)], {'force_sql_filters': True}):
            try:
                await self.middleware.call('vm.start', vm['id'])
            except Exception as e:
                self.middleware.logger.error(f'Failed to start VM {vm["name"]}: {e}')

    @private
    async def handle_shutdown(self):
        active = await self.middleware.call('vm.query', [('status.state', 'in', ACTIVE_STATES)])
        await asyncio.gather(*(_stop_one_vm(self.middleware, vm) for vm in active))


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
