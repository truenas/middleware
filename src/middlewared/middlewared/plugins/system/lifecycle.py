import asyncio

from middlewared.schema import accepts, Bool, Dict, Int, returns, Str
from middlewared.service import job, private, Service, no_auth_required, pass_app
from middlewared.utils import Popen, run

from .utils import lifecycle_conf, RE_KDUMP_CONFIGURED


class SystemService(Service):

    @private
    async def first_boot(self):
        return lifecycle_conf.SYSTEM_FIRST_BOOT

    @no_auth_required
    @accepts()
    @returns(Str('system_boot_identifier'))
    @pass_app()
    async def boot_id(self, app):
        """
        Returns an unique boot identifier.

        It is supposed to be unique every system boot.
        """
        # NOTE: this is used, at time of writing, by the UI
        # team to handle caching of web page assets. This
        # doesn't require authentication since our login page
        # also has information that is cached. Security team
        # is aware and the risk is minimal
        return lifecycle_conf.SYSTEM_BOOT_ID

    @accepts()
    @returns(Bool('system_ready'))
    async def ready(self):
        """
        Returns whether the system completed boot and is ready to use
        """
        return await self.middleware.call('system.state') != 'BOOTING'

    @accepts()
    @returns(Str('system_state', enum=['SHUTTING_DOWN', 'READY', 'BOOTING']))
    async def state(self):
        """
        Returns system state:
        "BOOTING" - System is booting
        "READY" - System completed boot and is ready to use
        "SHUTTING_DOWN" - System is shutting down
        """
        if lifecycle_conf.SYSTEM_SHUTTING_DOWN:
            return 'SHUTTING_DOWN'
        if lifecycle_conf.SYSTEM_READY:
            return 'READY'
        return 'BOOTING'

    @accepts(Dict('system-reboot', Int('delay', required=False), required=False))
    @returns()
    @job()
    async def reboot(self, job, options):
        """
        Reboots the operating system.

        Emits an "added" event of name "system" and id "reboot".
        """
        if options is None:
            options = {}

        self.middleware.send_event('system.reboot', 'ADDED')

        delay = options.get('delay')
        if delay:
            await asyncio.sleep(delay)

        await run(['/sbin/shutdown', '-r', 'now'])

    @accepts(Dict('system-shutdown', Int('delay', required=False), required=False))
    @returns()
    @job()
    async def shutdown(self, job, options):
        """
        Shuts down the operating system.

        An "added" event of name "system" and id "shutdown" is emitted when shutdown is initiated.
        """
        if options is None:
            options = {}

        delay = options.get('delay')
        if delay:
            await asyncio.sleep(delay)

        await run(['/sbin/poweroff'])


async def _event_system_ready(middleware, event_type, args):
    lifecycle_conf.SYSTEM_READY = True

    if (await middleware.call('system.advanced.config'))['kdump_enabled']:
        cp = await run(['kdump-config', 'status'], check=False)
        if cp.returncode:
            middleware.logger.error('Failed to retrieve kdump-config status: %s', cp.stderr.decode())
        else:
            if not RE_KDUMP_CONFIGURED.findall(cp.stdout.decode()):
                await middleware.call('alert.oneshot_create', 'KdumpNotReady', None)
            else:
                await middleware.call('alert.oneshot_delete', 'KdumpNotReady', None)
    else:
        await middleware.call('alert.oneshot_delete', 'KdumpNotReady', None)

    if await middleware.call('system.first_boot'):
        middleware.create_task(middleware.call('usage.firstboot'))


async def _event_system_shutdown(middleware, event_type, args):
    lifecycle_conf.SYSTEM_SHUTTING_DOWN = True


async def setup(middleware):
    middleware.event_subscribe('system.ready', _event_system_ready)
    middleware.event_subscribe('system.shutdown', _event_system_shutdown)
