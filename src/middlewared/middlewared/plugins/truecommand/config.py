from __future__ import annotations

import asyncio
from typing import Any

from middlewared.api.current import (
    TRUECOMMAND_CONNECTING_STATUS_REASON,
    TRUECOMMAND_DISABLED_ON_STANDBY_STATUS_REASON,
    TruecommandEntry,
    TruecommandStatus,
    TruecommandStatusReason,
    TruecommandUpdate,
)
from middlewared.service import ConfigServicePart, ValidationErrors
import middlewared.sqlalchemy as sa

from .portal import register_with_portal
from .state import dismiss_alerts, event_config, get_status, set_status
from .wireguard import (
    generate_wg_keys,
    start_truecommand_service,
    stop_truecommand_service,
    wireguard_connection_health,
)

TRUECOMMAND_UPDATE_LOCK = asyncio.Lock()


class TrueCommandModel(sa.Model):
    __tablename__ = 'system_truecommand'

    id = sa.Column(sa.Integer(), primary_key=True)
    api_key = sa.Column(sa.EncryptedText(), default=None, nullable=True)
    api_key_state = sa.Column(sa.String(128), default='DISABLED', nullable=True)
    wg_public_key = sa.Column(sa.String(255), default=None, nullable=True)
    wg_private_key = sa.Column(sa.EncryptedText(), default=None, nullable=True)
    wg_address = sa.Column(sa.String(255), default=None, nullable=True)
    tc_public_key = sa.Column(sa.String(255), default=None, nullable=True)
    endpoint = sa.Column(sa.String(255), default=None, nullable=True)
    remote_address = sa.Column(sa.String(255), default=None, nullable=True)
    enabled = sa.Column(sa.Boolean(), default=False)


class TruecommandConfigServicePart(ConfigServicePart[TruecommandEntry]):
    _datastore = 'system.truecommand'
    _entry = TruecommandEntry

    async def extend(self, data: dict[str, Any]) -> dict[str, Any]:
        for key in ('wg_public_key', 'wg_private_key', 'tc_public_key', 'endpoint', 'wg_address'):
            data.pop(key)

        # Pop unconditionally so the standby controller path below also strips it - api_key_state
        # is not a field on the entry and would otherwise fail validation on the standby node.
        api_key_state = data.pop('api_key_state')

        # In database we will have CONNECTED when the portal has approved the key
        # Connecting basically represents 2 phases - where we wait for TC to connect to
        # NAS and where we are waiting to hear back from the portal after registration
        status_reason = None
        if await self.middleware.call('failover.is_single_master_node'):
            if TruecommandStatus(
                api_key_state
            ) == TruecommandStatus.CONNECTED and get_status() == TruecommandStatus.CONNECTING:
                if await wireguard_connection_health(self):
                    await set_status(self, TruecommandStatus.CONNECTED.value)
                else:
                    status_reason = TRUECOMMAND_CONNECTING_STATUS_REASON
        else:
            if get_status() != TruecommandStatus.DISABLED:
                await set_status(self, TruecommandStatus.DISABLED.value)
            status_reason = TRUECOMMAND_DISABLED_ON_STANDBY_STATUS_REASON

        data['remote_ip_address'] = data['remote_url'] = data.pop('remote_address')
        if data['remote_ip_address']:
            data['remote_ip_address'] = data.pop('remote_ip_address').split('/', 1)[0]
            data['remote_url'] = f'http://{data["remote_ip_address"]}/'

        status = get_status()
        data.update({
            'status': status.value,
            'status_reason': status_reason or TruecommandStatusReason.__members__[status.value].value
        })
        return data

    async def do_update(self, data: TruecommandUpdate) -> TruecommandEntry:
        # We have following cases worth mentioning wrt updating TC credentials
        # 1) User enters API Key and enables the service
        # 2) User disables the service
        # 3) User changes API Key and service is enabled
        #
        # Another point to document is how we intend to poll, we are going to send a request to iX Portal
        # and if it returns active state with the data we require for wireguard connection, we mark the
        # API Key as connected. As long as we keep polling iX portal, we are going to be in a connecting state,
        # no matter what errors we are getting from the polling bits. The failure case is when iX Portal sends
        # us the state "unknown", which after confirming with Ken means that the portal has revoked the api key
        # in question and we no longer use it. In this case we are going to stop polling and mark the connection
        # as failed.
        #
        # For case (1), when user enters API key and enables the service, we are first going to generate wg keys
        # if they haven't been generated already. Then we are going to register the new api key with ix portal.
        # Once done, we are going to start polling. If polling gets us in success state, we are going to start
        # wireguard connection, for the other case, we are going to emit an event with truecommand failure status.
        #
        # For case (2), if the service was running previously, we do nothing except for stopping wireguard and
        # ensuring it is not started at boot as well. The connection details remain secure in the database.
        #
        # For case (3), everything is similar to how we handle case (1), however we are going to stop wireguard
        # if it was running with previous api key credentials.
        async with TRUECOMMAND_UPDATE_LOCK:
            old = await self.middleware.call('datastore.config', self._datastore)
            new = old.copy()
            new.update(data.model_dump(exclude_unset=True, expose_secrets=True))

            verrors = ValidationErrors()
            if new['enabled'] and not new['api_key']:
                verrors.add(
                    'truecommand_update.api_key',
                    'API Key must be provided when Truecommand service is enabled.'
                )

            verrors.check()

            if all(old[k] == new[k] for k in ('enabled', 'api_key')):
                # Nothing changed
                return await self.config()

            polling_jobs = await self.middleware.call(
                'core.get_jobs', [
                    ['method', '=', 'truecommand.poll_api_for_status'], ['state', 'in', ['WAITING', 'RUNNING']]
                ]
            )
            for polling_job in polling_jobs:
                await self.middleware.call('core.job_abort', polling_job['id'])

            await set_status(self, TruecommandStatus.DISABLED.value)
            new['api_key_state'] = TruecommandStatus.DISABLED.value

            if old['api_key'] != new['api_key']:
                new.update({
                    'remote_address': None,
                    'endpoint': None,
                    'tc_public_key': None,
                    'wg_address': None,
                    'wg_public_key': None,
                    'wg_private_key': None,
                    'api_key_state': TruecommandStatus.DISABLED.value,
                })

            if new['enabled']:
                if not new['wg_public_key'] or not new['wg_private_key']:
                    new.update(**(await generate_wg_keys()))

                if old['api_key'] != new['api_key']:
                    await register_with_portal(self, new)
                    # Registration succeeded, we are good to poll now
                elif all(
                    new[k] for k in ('wg_address', 'wg_private_key', 'remote_address', 'endpoint', 'tc_public_key')
                ):
                    # Api key hasn't changed and we have wireguard details, let's please start wireguard in this case
                    await set_status(self, TruecommandStatus.CONNECTING.value)
                    new['api_key_state'] = TruecommandStatus.CONNECTED.value

            await dismiss_alerts(self, True)

            await self.middleware.call('datastore.update', self._datastore, old['id'], new)

            self.middleware.send_event('truecommand.config', 'CHANGED', fields=await event_config(self))

            # We are going to stop truecommand service with this update anyways as only 2 possible actions
            # can happen on update
            # 1) Service enabled/disabled
            # 2) Api Key changed
            await stop_truecommand_service(self)

            if new['enabled']:
                if new['api_key'] != old['api_key'] or any(
                    not new[k] for k in ('wg_address', 'wg_private_key', 'remote_address', 'endpoint', 'tc_public_key')
                ):
                    # We are going to start polling here
                    await self.call2(self.s.truecommand.poll_api_for_status)
                else:
                    # User just enabled the service after disabling it - we have wireguard details and
                    # we can initiate the connection. If it is not good, health check will fail and we will
                    # poll iX Portal to see what's up. Let's just start wireguard now
                    await start_truecommand_service(self)

                await self.call2(self.s.truesearch.configure)

            return await self.config()
