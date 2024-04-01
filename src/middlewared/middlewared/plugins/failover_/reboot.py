import asyncio
import errno
import time

from middlewared.schema import accepts, returns
from middlewared.service import CallError, job, Service


class FailoverService(Service):

    class Config:
        cli_private = True
        role_prefix = 'FAILOVER'

    @accepts()
    @returns()
    @job(lock='reboot_standby')
    async def reboot_standby(self, job):
        """
        Reboot the standby node and wait for it to come back online.
        """
        remote_boot_id = await self.middleware.call('failover.call_remote', 'system.boot_id')

        job.set_progress(5, 'Rebooting standby controller')
        await self.middleware.call(
            'failover.call_remote', 'failover.become_passive', [], {'raise_connect_error': False, 'timeout': 20}
        )

        job.set_progress(30, 'Waiting on the Standby Controller to reboot')
        try:
            retry_time = time.monotonic()
            shutdown_timeout = 90  # seconds
            while time.monotonic() - retry_time < shutdown_timeout:
                await self.middleware.call('failover.call_remote', 'core.ping', [], {'timeout': 5})
                await asyncio.sleep(5)
        except CallError:
            pass
        else:
            raise CallError(
                f'Timed out waiting {shutdown_timeout} seconds for the standby controller to reboot',
                errno.ETIMEDOUT
            )

        job.set_progress(60, 'Waiting for the Standby Controller to come back online')

        # Wait for the standby controller to come back online and report as being ready
        if not await self.middleware.call('failover.upgrade_waitstandby'):
            raise CallError('Timed out waiting for the standby controller to upgrade', errno.ETIMEDOUT)

        # We captured the boot_id of the standby controller before we rebooted it
        # This variable represents a 1-time unique boot id. It's supposed to be different
        # every time the system boots up. If this check is True, then it's safe to say
        # that the remote system never rebooted
        if remote_boot_id == await self.middleware.call('failover.call_remote', 'system.boot_id'):
            raise CallError('Standby Controller failed to reboot')

        job.set_progress(100, 'Standby Controller has been rebooted successfully')
        return True
