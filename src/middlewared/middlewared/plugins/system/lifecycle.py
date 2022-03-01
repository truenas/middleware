import asyncio

from middlewared.schema import accepts, Bool, Dict, Int, returns, Str
from middlewared.service import job, private, Service
from middlewared.utils import Popen

from .utils import lifecycle_conf


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
