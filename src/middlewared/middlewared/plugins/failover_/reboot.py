# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions
import asyncio
import errno
import time

from middlewared.schema import accepts, Bool, Dict, returns
from middlewared.service import CallError, job, private, Service


class FailoverRebootService(Service):

    class Config:
        cli_namespace = 'system.failover.reboot'
        namespace = 'failover.reboot'

    @private
    async def retrieve_boot_ids(self):
        return {
            await self.middleware.call('failover.node'): await self.middleware.call('system.boot_id'),
            await self.middleware.call(
                'failover.call_remote', 'failover.node', [], {'raise_connect_error': False}
            ): await self.middleware.call(
                'failover.call_remote', 'system.boot_id', [], {'raise_connect_error': False}
            ),
        }

    @accepts(roles=['FAILOVER_READ'])
    @returns(Dict(
        Bool('reboot_required'),
        Bool('node_a_reboot_required'),
        Bool('node_b_reboot_required'),
    ))
    async def info(self):
        """
        Returns whether a reboot is required for failover/security system configuration changes to take effect.
        """
        return await self.check_reboot_required()

    @accepts(roles=['FAILOVER_READ'])
    @returns(Bool())
    async def required(self):
        """
        Returns whether a reboot is required for failover/security system configuration changes to take effect.
        """
        return (await self.check_reboot_required())['reboot_required']

    @private
    async def check_reboot_required(self):
        fips_change_info = await self.middleware.call('keyvalue.get', 'fips_toggled', False)
        if not fips_change_info:
            return {
                'reboot_required': False,
                'node_a_reboot_required': False,
                'node_b_reboot_required': False,
            }

        existing_boot_ids = await self.retrieve_boot_ids()
        info = {
            # We retrieve A/B safely just to be sure that we don't have any issues
            # Not sure what the best way to handle it would be if we were not able to connect to remote
            'node_a_reboot_required': existing_boot_ids.get('A') == fips_change_info.get('A'),
            'node_b_reboot_required': existing_boot_ids.get('B') == fips_change_info.get('B'),
            'reboot_required': False,
        }
        if info['node_a_reboot_required'] or info['node_b_reboot_required']:
            info['reboot_required'] = True
        else:
            await self.middleware.call('keyvalue.delete', 'fips_toggled')

        return info

    @accepts(roles=['FULL_ADMIN'])
    @returns()
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
