# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions
import asyncio
import errno
import time

from middlewared.api import api_method
from middlewared.api.current import FailoverRebootRequiredArgs, FailoverRebootRequiredResult
from middlewared.schema import accepts, Bool, Dict, UUID, returns
from middlewared.service import CallError, job, private, Service

FIPS_KEY = 'fips_toggled'


class FailoverRebootService(Service):

    class Config:
        cli_namespace = 'system.failover.reboot'
        namespace = 'failover.reboot'

    reboot_reasons : dict[str, str] = {}

    @private
    async def add_reason(self, key: str, value: str):
        """
        Adds a reason on why this system needs a reboot.
        :param key: unique identifier for the reason.
        :param value: text explanation for the reason.
        """
        self.reboot_reasons[key] = value

    @private
    async def boot_ids(self):
        info = {
            'this_node': {'id': await self.middleware.call('system.boot_id')},
            'other_node': {'id': None}
        }
        try:
            info['other_node']['id'] = await self.middleware.call(
                'failover.call_remote', 'system.boot_id', [], {
                    'raise_connect_error': False, 'timeout': 2, 'connect_timeout': 2,
                }
            )
        except Exception:
            self.logger.warning('Unexpected error querying remote node boot id', exc_info=True)

        return info

    @private
    async def info_impl(self):
        # initial state
        current_info = await self.boot_ids()
        current_info['this_node'].update({'reboot_required': None, 'reboot_required_reasons': []})
        current_info['other_node'].update({'reboot_required': None, 'reboot_required_reasons': []})

        fips_change_info = await self.middleware.call('keyvalue.get', FIPS_KEY, False)
        if not fips_change_info:
            for i in current_info:
                current_info[i]['reboot_required'] = False
        else:
            for key in ('this_node', 'other_node'):
                current_info[key]['reboot_required'] = all((
                    fips_change_info[key]['id'] == current_info[key]['id'],
                    fips_change_info[key]['reboot_required']
                ))
                if current_info[key]['reboot_required']:
                    current_info[key]['reboot_required_reasons'].append('FIPS configuration was changed.')

            if all((
                current_info['this_node']['reboot_required'] is False,
                current_info['other_node']['reboot_required'] is False,
            )):
                # no reboot required for either controller so delete
                await self.middleware.call('keyvalue.delete', FIPS_KEY)

        for reason in self.reboot_reasons.values():
            current_info['this_node']['reboot_required'] = True
            current_info['this_node']['reboot_required_reasons'].append(reason)

        return current_info

    @api_method(FailoverRebootRequiredArgs, FailoverRebootRequiredResult, roles=['FAILOVER_READ'])
    async def info(self):
        """Returns the local and remote nodes boot_ids along with their
        reboot statuses (i.e. does a reboot need to take place)"""
        return await self.info_impl()

    @accepts(roles=['FAILOVER_READ'])
    @returns(Bool())
    async def required(self):
        """Returns whether this node needs to be rebooted for failover/security
        system configuration changes to take effect."""
        # TODO: should we raise Callerror/ValidationError if reboot_required is None?
        return (await self.info())['this_node']['reboot_required'] is True

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
