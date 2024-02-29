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
            'failover.call_remote', 'system.reboot',
            [{'delay': 5}],
            {'job': True}
        )
        # SCALE is using systemd and at the time of writing this, the
        # DefaultTimeoutStopSec setting hasn't been changed and so
        # defaults to 90 seconds. This means when the system is sent the
        # shutdown signal, all the associated user-space programs are
        # asked to be shutdown. If any of those take longer than 90
        # seconds to respond to SIGTERM then the program is sent SIGKILL.
        # Finally, if after 90 seconds the standby controller is still
        # responding to remote requests then play it safe and assume the
        # reboot failed (this should be rare but my future self will
        # appreciate the fact I wrote this out because of the inevitable
        # complexities of gluster/k8s/vms etc for which I predict
        # will exhibit this behavior :P )
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

        # Wait for the standby controller to come back online and report as being ready
        if not await self.middleware.call('failover.upgrade_waitstandby'):
            raise CallError('Timed out waiting for the standby controller to upgrade', errno.ETIMEDOUT)

        # We captured the boot_id of the standby controller before we rebooted it
        # This variable represents a 1-time unique boot id. It's supposed to be different
        # every time the system boots up. If this check is True, then it's safe to say
        # that the remote system never rebooted
        if remote_boot_id == await self.middleware.call('failover.call_remote', 'system.boot_id'):
            raise CallError('Standby Controller failed to reboot')

        return True
