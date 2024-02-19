import asyncio

import middlewared.sqlalchemy as sa

from middlewared.schema import Bool, Dict, Int, IPAddr, Password, Str
from middlewared.service import accepts, ConfigService, private, ValidationErrors
from middlewared.validators import Range

from .enums import Status, StatusReason

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


class TruecommandService(ConfigService):

    STATUS = Status.DISABLED

    class Config:
        datastore = 'system.truecommand'
        datastore_extend = 'truecommand.tc_extend'
        cli_namespace = 'system.truecommand'

    ENTRY = Dict(
        'truecommand_entry',
        Int('id', required=True),
        Password('api_key', required=True, null=True),
        Str('status', required=True, enum=[s.value for s in Status]),
        Str('status_reason', required=True, enum=[s.value for s in StatusReason]),
        Str('remote_url', required=True, null=True),
        IPAddr('remote_ip_address', required=True, null=True),
        Bool('enabled', required=True),
    )

    @private
    async def tc_extend(self, config):
        for key in ('wg_public_key', 'wg_private_key', 'tc_public_key', 'endpoint', 'wg_address'):
            config.pop(key)

        # In database we will have CONNECTED when the portal has approved the key
        # Connecting basically represents 2 phases - where we wait for TC to connect to
        # NAS and where we are waiting to hear back from the portal after registration
        status_reason = None
        if await self.middleware.call('failover.is_single_master_node'):
            if Status(config.pop('api_key_state')) == self.STATUS.CONNECTED and self.STATUS == Status.CONNECTING:
                if await self.middleware.call('truecommand.wireguard_connection_health'):
                    await self.set_status(Status.CONNECTED.value)
                else:
                    status_reason = 'Waiting for connection from Truecommand.'
        else:
            if self.STATUS != Status.DISABLED:
                await self.set_status(Status.DISABLED.value)
            status_reason = 'Truecommand service is disabled on standby controller'

        config['remote_ip_address'] = config['remote_url'] = config.pop('remote_address')
        if config['remote_ip_address']:
            config['remote_ip_address'] = config.pop('remote_ip_address').split('/', 1)[0]
            config['remote_url'] = f'http://{config["remote_ip_address"]}/'

        config.update({
            'status': self.STATUS.value,
            'status_reason': status_reason or StatusReason.__members__[self.STATUS.value].value
        })
        return config

    @accepts(
        Dict(
            'truecommand_update',
            Bool('enabled'),
            Password('api_key', null=True, validators=[Range(min=16, max=16)]),
        )
    )
    async def do_update(self, data):
        """
        Update Truecommand service settings.

        `api_key` is a valid API key generated by iX Portal.
        """
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
            old = await self.middleware.call('datastore.config', self._config.datastore)
            new = old.copy()
            new.update(data)

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

            await self.set_status(Status.DISABLED.value)
            new['api_key_state'] = Status.DISABLED.value

            if old['api_key'] != new['api_key']:
                new.update({
                    'remote_address': None,
                    'endpoint': None,
                    'tc_public_key': None,
                    'wg_address': None,
                    'wg_public_key': None,
                    'wg_private_key': None,
                    'api_key_state': Status.DISABLED.value,
                })

            if new['enabled']:
                if not new['wg_public_key'] or not new['wg_private_key']:
                    new.update(**(await self.middleware.call('truecommand.generate_wg_keys')))

                if old['api_key'] != new['api_key']:
                    await self.middleware.call('truecommand.register_with_portal', new)
                    # Registration succeeded, we are good to poll now
                elif all(
                    new[k] for k in ('wg_address', 'wg_private_key', 'remote_address', 'endpoint', 'tc_public_key')
                ):
                    # Api key hasn't changed and we have wireguard details, let's please start wireguard in this case
                    await self.set_status(Status.CONNECTING.value)
                    new['api_key_state'] = Status.CONNECTED.value

            await self.dismiss_alerts(True)

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                old['id'],
                new
            )

            self.middleware.send_event('truecommand.config', 'CHANGED', fields=(await self.event_config()))

            # We are going to stop truecommand service with this update anyways as only 2 possible actions
            # can happen on update
            # 1) Service enabled/disabled
            # 2) Api Key changed
            await self.middleware.call('truecommand.stop_truecommand_service')

            if new['enabled']:
                if new['api_key'] != old['api_key'] or any(
                    not new[k] for k in ('wg_address', 'wg_private_key', 'remote_address', 'endpoint', 'tc_public_key')
                ):
                    # We are going to start polling here
                    await self.middleware.call('truecommand.poll_api_for_status')
                else:
                    # User just enabled the service after disabling it - we have wireguard details and
                    # we can initiate the connection. If it is not good, health check will fail and we will
                    # poll iX Portal to see what's up. Let's just start wireguard now
                    await self.middleware.call('truecommand.start_truecommand_service')

            return await self.config()

    @private
    async def set_status(self, new_status):
        assert new_status in Status.__members__
        self.STATUS = Status(new_status)
        self.middleware.send_event('truecommand.config', 'CHANGED', fields=(await self.event_config()))

    @private
    async def dismiss_alerts(self, dismiss_health=False, dismiss_health_only=False):
        # We do not dismiss health by default because it's possible that the key has not been revoked
        # and it's just that TC has not connected to TN in 30 minutes, so we only should dismiss it when
        # we update TC service or the health is okay now with the service running or when service is not running
        health_alerts = {'TruecommandConnectionHealth', 'TruecommandContainerHealth'}
        non_health_alerts = {'TruecommandConnectionDisabled', 'TruecommandConnectionPending'}
        if dismiss_health_only:
            to_dismiss_alerts = health_alerts
        else:
            to_dismiss_alerts = health_alerts | non_health_alerts if dismiss_health else non_health_alerts
        for klass in to_dismiss_alerts:
            await self.middleware.call('alert.oneshot_delete', klass, None)

    @private
    async def event_config(self):
        config = await self.config()
        config.pop('api_key', None)
        return config
