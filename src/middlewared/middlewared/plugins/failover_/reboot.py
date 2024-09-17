# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions
import asyncio
from dataclasses import dataclass
import errno
import time

from middlewared.api import api_method
from middlewared.api.current import (
    FailoverRebootInfoArgs, FailoverRebootInfoResult,
    FailoverRebootOtherNodeArgs, FailoverRebootOtherNodeResult,
)
from middlewared.service import CallError, job, private, Service


@dataclass
class RemoteRebootReason:
    # Boot ID for which the reboot is required. `None` means that the system must be rebooted when it comes online.
    boot_id: str | None
    reason: str


class FailoverRebootService(Service):

    class Config:
        cli_namespace = 'system.failover.reboot'
        namespace = 'failover.reboot'

    remote_reboot_reasons: dict[str, RemoteRebootReason] = {}

    @private
    async def add_remote_reason(self, code: str, reason: str):
        """
        Adds a reason for why the remote system needs a reboot.
        This will be appended to the list of the reasons that the remote node itself returns.
        :param code: unique identifier for the reason.
        :param reason: text explanation for the reason.
        """
        try:
            boot_id = await self.middleware.call('failover.call_remote', 'system.boot_id', [], {
                'raise_connect_error': False,
                'timeout': 2,
                'connect_timeout': 2,
            })
        except Exception:
            self.logger.warning('Unexpected error querying remote reboot boot id', exc_info=True)
            # Remote system is inaccessible, so, when it comes back, another reboot will be required.
            boot_id = None

        self.remote_reboot_reasons[code] = RemoteRebootReason(boot_id, reason)

        await self.send_event()

    @api_method(FailoverRebootInfoArgs, FailoverRebootInfoResult, roles=['FAILOVER_READ'])
    async def info(self):
        changed = False

        try:
            other_node = await self.middleware.call('failover.call_remote', 'system.reboot.info', [], {
                'raise_connect_error': False,
                'timeout': 2,
                'connect_timeout': 2,
            })
        except Exception:
            self.logger.warning('Unexpected error querying remote reboot info', exc_info=True)
            other_node = None

        if other_node is not None:
            for remote_reboot_reason_code, remote_reboot_reason in list(self.remote_reboot_reasons.items()):
                if remote_reboot_reason.boot_id is None:
                    # This reboot reason was added while the remote node was not functional.
                    # In that case, when the remote system comes online, an additional reboot is required.
                    remote_reboot_reason.boot_id = other_node['boot_id']
                    changed = True

                if remote_reboot_reason.boot_id == other_node['boot_id']:
                    other_node['reboot_required_reasons'].append({
                        'code': remote_reboot_reason_code,
                        'reason': remote_reboot_reason.reason,
                    })
                else:
                    # The system was rebooted, this reason is not valid anymore
                    self.remote_reboot_reasons.pop(remote_reboot_reason_code)
                    changed = True

        info = {
            'this_node': await self.middleware.call('system.reboot.info'),
            'other_node': other_node,
        }

        if changed:
            await self.send_event(info)

        return info

    @api_method(FailoverRebootOtherNodeArgs, FailoverRebootOtherNodeResult, roles=['FULL_ADMIN'])
    @job(lock='reboot_standby')
    async def other_node(self, job):
        """
        Reboot the other node and wait for it to come back online.

        NOTE: This makes very few checks on HA systems. You need to
            know what you're doing before calling this.
        """
        if not await self.middleware.call('failover.licensed'):
            return

        remote_boot_id = await self.middleware.call('failover.call_remote', 'system.boot_id')

        job.set_progress(5, 'Rebooting other controller')
        await self.middleware.call(
            'failover.call_remote', 'failover.become_passive', [], {'raise_connect_error': False, 'timeout': 20}
        )

        job.set_progress(30, 'Waiting on the other controller to go offline')
        try:
            retry_time = time.monotonic()
            timeout = 90  # seconds
            while time.monotonic() - retry_time < timeout:
                await self.middleware.call('failover.call_remote', 'core.ping', [], {'timeout': 5})
                await asyncio.sleep(5)
        except CallError:
            pass
        else:
            raise CallError(
                f'Timed out after {timeout}seconds waiting for the other controller to come back online',
                errno.ETIMEDOUT
            )

        job.set_progress(60, 'Waiting for the other controller to come back online')
        if not await self.middleware.call('failover.upgrade_waitstandby'):
            # FIXME: `upgrade_waitstandby` is a really poor name for a method that
            # just waits on the other controller to come back online and be ready
            raise CallError('Timed out waiting for the other controller to come online', errno.ETIMEDOUT)

        # We captured the boot_id of the standby controller before we rebooted it
        # This variable represents a 1-time unique boot id. It's supposed to be different
        # every time the system boots up. If this check is True, then it's safe to say
        # that the remote system never rebooted
        if remote_boot_id == await self.middleware.call('failover.call_remote', 'system.boot_id'):
            raise CallError('Other controller failed to reboot')

        job.set_progress(100, 'Other controller rebooted successfully')
        return True

    @private
    async def send_event(self, info=None):
        if info is None:
            info = await self.info()

        self.middleware.send_event('failover.reboot.info', 'CHANGED', id=None, fields=info)


async def reboot_info(middleware, *args, **kwargs):
    await middleware.call('failover.reboot.send_event')


def remote_reboot_info(middleware, *args, **kwargs):
    middleware.call_sync('failover.reboot.send_event', background=True)


async def setup(middleware):
    middleware.event_register('failover.reboot.info', 'Sent when a system reboot is required.', roles=['FAILOVER_READ'])

    middleware.event_subscribe('system.reboot.info', remote_reboot_info)
    await middleware.call('failover.remote_on_connect', remote_reboot_info)
    await middleware.call('failover.remote_subscribe', 'system.reboot.info', remote_reboot_info)
