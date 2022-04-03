import asyncio

from middlewared.schema import accepts, Bool, Dict, Int, returns, Str
from middlewared.service import job, private, Service
from middlewared.utils import Popen, run

from .utils import lifecycle_conf, RE_KDUMP_CONFIGURED


class SystemService(Service):

    @private
    async def first_boot(self):
        return lifecycle_conf.SYSTEM_FIRST_BOOT

    @accepts()
    @returns(Str('system_boot_identifier'))
    async def boot_id(self):
        """
        Returns an unique boot identifier.

        It is supposed to be unique every system boot.
        """
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

        self.middleware.send_event('system', 'ADDED', id='reboot', fields={'description': 'System is going to reboot'})

        delay = options.get('delay')
        if delay:
            await asyncio.sleep(delay)

        await Popen(['/sbin/shutdown', '-r', 'now'])

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

        await Popen(['/sbin/poweroff'])


async def _update_birthday(middleware):
    while True:
        birthday = await middleware.call('system.get_synced_clock_time')
        if birthday:
            middleware.logger.debug('Updating birthday data')
            # update db with new birthday
            settings = await middleware.call('datastore.config', 'system.settings')
            await middleware.call(
                'datastore.update', 'system.settings', settings['id'], {'stg_birthday': birthday}, {'ha_sync': False}
            )
            break
        else:
            await asyncio.sleep(300)


async def _event_system(middleware, event_type, args):

    if args['id'] == 'ready':
        lifecycle_conf.SYSTEM_READY = True

        # Check if birthday is already set
        birthday = await middleware.call('system.birthday')
        if birthday is None:
            # try to set birthday in background
            asyncio.ensure_future(_update_birthday(middleware))

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
            asyncio.ensure_future(middleware.call('usage.firstboot'))

    if args['id'] == 'shutdown':
        lifecycle_conf.SYSTEM_SHUTTING_DOWN = True


async def setup(middleware):
    middleware.event_subscribe('system', _event_system)
