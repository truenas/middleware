# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions
import asyncio
from dataclasses import asdict, dataclass
import errno
import time

from middlewared.api import api_method, Event
from middlewared.api.current import (
    FailoverRebootInfoArgs, FailoverRebootInfoResult,
    FailoverRebootOtherNodeArgs, FailoverRebootOtherNodeResult,
    FailoverRebootInfoChangedEvent,
)
from middlewared.plugins.system.reboot import RebootReason
from middlewared.service import CallError, job, private, Service
from middlewared.utils.threading import run_coro_threadsafe


@dataclass
class RemoteRebootReason:
    # Boot ID for which the reboot is required. `None` means that the system must be rebooted when it comes online.
    boot_id: str | None
    reason: str


class FailoverRebootService(Service):

    class Config:
        cli_namespace = 'system.failover.reboot'
        namespace = 'failover.reboot'
        events = [
            Event(
                name='failover.reboot.info',
                description='Sent when a system reboot is required.',
                roles=['FAILOVER_READ'],
                models={'CHANGED': FailoverRebootInfoChangedEvent},
            )
        ]

    remote_reboot_reasons_key: str
    remote_reboot_reasons: dict[str, RemoteRebootReason]
    loaded = False

    @private
    async def add_remote_reason(self, code: str, reason: str):
        """
        Adds a reason for why the remote system needs a reboot.
        This will be appended to the list of the reasons that the remote node itself returns.
        :param code: unique identifier for the reason.
        :param reason: text explanation for the reason.
        """
        if not self.loaded:
            raise CallError(f'Cannot add remote reboot reason before they are loaded: ({code},{reason})')

        try:
            boot_id = await self.middleware.call('failover.call_remote', 'system.boot_id', [], {
                'raise_connect_error': False,
                'timeout': 2,
                'connect_timeout': 2,
            })
        except Exception as e:
            if not (isinstance(e, CallError) and e.errno == CallError.ENOMETHOD):
                self.logger.warning('Unexpected error querying remote reboot boot id', exc_info=True)

            # Remote system is inaccessible, so, when it comes back, another reboot will be required.
            boot_id = None

        self.remote_reboot_reasons[code] = RemoteRebootReason(boot_id, reason)
        await self.persist_remote_reboot_reasons()

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
        except Exception as e:
            self.logger.warning(f'Unexpected error querying remote reboot info: {e}')
            other_node = None
        else:
            if other_node is None:
                # Legacy system that does not support `system.reboot.info`
                try:
                    other_node_boot_id = await self.middleware.call('failover.call_remote', 'system.boot_id', [], {
                        'raise_connect_error': False,
                        'timeout': 2,
                        'connect_timeout': 2,
                    })
                except Exception as e:
                    # Legacy system that does not have `system.boot_id`, upgrading this is not supported
                    self.logger.warning(f'Unexpected error querying remote reboot info: {e}')
                    other_node = None
                else:
                    if other_node_boot_id is not None:
                        # Try querying `system.reboot.info` once more in case the system is really upgraded, and the
                        # failure was just a hiccup.
                        try:
                            other_node = await self.middleware.call('failover.call_remote', 'system.reboot.info', [], {
                                'raise_connect_error': False,
                                'timeout': 2,
                                'connect_timeout': 2,
                            })
                        except Exception:
                            other_node = None

                        if other_node is None:
                            # It is indeed a legacy system. Mark it as needing reboot
                            self.remote_reboot_reasons.setdefault(RebootReason.UPGRADE.name, RemoteRebootReason(
                                boot_id=None,
                                reason=RebootReason.UPGRADE.value,
                            ))
                            # Fake `system.reboot.info` so that the code below functions properly
                            other_node = {
                                'boot_id': other_node_boot_id,
                                'reboot_required_reasons': [],
                            }

        if other_node is not None:
            for remote_reboot_reason_code, remote_reboot_reason in list(self._remote_reboot_reasons_items()):
                if remote_reboot_reason.boot_id is None:
                    # This reboot reason was added while the remote node was not functional.
                    # In that case, when the remote system comes online, an additional reboot is required.
                    self.logger.debug(
                        f"Setting unbound remote reboot reason {remote_reboot_reason!r} boot ID to "
                        f"{other_node['boot_id']!r}"
                    )
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
            await self.persist_remote_reboot_reasons()

            await self.send_event(info)

        return info

    @api_method(FailoverRebootOtherNodeArgs, FailoverRebootOtherNodeResult, roles=['FULL_ADMIN'])
    @job(lock='reboot_standby')
    async def other_node(self, job, options):
        """
        Reboot the other node and wait for it to come back online.

        NOTE: This makes very few checks on HA systems. You need to
            know what you're doing before calling this.
        """
        if not await self.middleware.call('failover.licensed'):
            return

        job.set_progress(0, 'Checking other controller boot environment')
        current_be_id = (await self.middleware.call(
            'boot.environment.query',
            [['active', '=', True]],
            {'get': True},
        ))['id']
        remote_be_changed = await self._ensure_remote_be(current_be_id)

        remote_boot_id = await self.middleware.call('failover.call_remote', 'system.boot_id')

        job.set_progress(5, 'Rebooting other controller')
        if remote_be_changed or options['graceful']:
            # We try to call `system.reboot` with two possible signatures: first, with reboot reason, the actual one,
            # and second, without reboot reason, the legacy one. One will work on 25.04+ and fail silently on 24.10
            # (due to `job_return: true`), the other vice versa.
            await self.middleware.call(
                'failover.call_remote',
                'system.reboot',
                [options['reason'], {'delay': 5}],
                {
                    'job': True,
                    'job_return': True,
                },
            )
            await self.middleware.call(
                'failover.call_remote',
                'system.reboot',
                [{'delay': 5}],
                {
                    'job': True,
                    'job_return': True,
                },
            )
        else:
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
        if not (await (await self.middleware.call('failover.wait_other_node')).wait(raise_error=True)):
            raise CallError('Timed out waiting for the other controller to come online', errno.ETIMEDOUT)

        # We captured the boot_id of the standby controller before we rebooted it
        # This variable represents a 1-time unique boot id. It's supposed to be different
        # every time the system boots up. If this check is True, then it's safe to say
        # that the remote system never rebooted
        if remote_boot_id == await self.middleware.call('failover.call_remote', 'system.boot_id'):
            raise CallError('Other controller failed to reboot')

        job.set_progress(100, 'Other controller rebooted successfully')

    def _remote_reboot_reasons_items(self):
        if self.loaded:
            return self.remote_reboot_reasons.items()
        return {}

    async def _ensure_remote_be(self, id_: str):
        try:
            remote_be_id = (await self.middleware.call(
                'failover.call_remote',
                'boot.environment.query',
                [
                    [['active', '=', True]],
                    {'get': True},
                ],
            ))['id']

            boot_environment_plugin = 'boot.environment'
        except CallError as e:
            if e.errno != CallError.ENOMETHOD:
                raise

            remote_be_id = (await self.middleware.call(
                'failover.call_remote',
                'bootenv.query',
                [
                    [['active', 'rin', 'R']],
                    {'get': True},
                ],
            ))['id']

            boot_environment_plugin = 'bootenv'

        if remote_be_id == id_:
            return False

        await self.middleware.call(
            'failover.call_remote',
            f'{boot_environment_plugin}.activate',
            [id_],
        )
        return True

    @private
    async def send_event(self, info=None):
        if info is None:
            info = await self.info()

        self.middleware.send_event('failover.reboot.info', 'CHANGED', id=None, fields=info)

    @private
    async def load_remote_reboot_reasons(self):
        self.remote_reboot_reasons_key = f'remote_reboot_reasons_{await self.middleware.call("failover.node")}'
        self.remote_reboot_reasons = {
            k: RemoteRebootReason(**v)
            for k, v in (await self.call2(self.s.keyvalue.get, self.remote_reboot_reasons_key, {})).items()
        }
        self.loaded = True

    @private
    async def persist_remote_reboot_reasons(self):
        await self.call2(self.s.keyvalue.set, self.remote_reboot_reasons_key, {
            k: asdict(v)
            for k, v in self.remote_reboot_reasons.items()
        })

    @private
    async def discard_unbound_remote_reboot_reasons(self):
        for k, v in list(self.remote_reboot_reasons.items()):
            if v.boot_id is None:
                self.remote_reboot_reasons.pop(k)


async def system_reboot_info_handler(middleware, *args, **kwargs):
    middleware.create_task(middleware.call('failover.reboot.send_event'))


def remote_reboot_info(middleware, *args, **kwargs):
    run_coro_threadsafe(middleware.call('failover.reboot.send_event'), loop=middleware.loop)


async def setup(middleware):
    await middleware.call('failover.reboot.load_remote_reboot_reasons')

    middleware.event_subscribe('system.reboot.info', system_reboot_info_handler)
    await middleware.call('failover.remote_on_connect', remote_reboot_info)
    await middleware.call('failover.remote_subscribe', 'system.reboot.info', remote_reboot_info)
