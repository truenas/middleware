import asyncio
import enum
import requests
import subprocess

import middlewared.sqlalchemy as sa

from middlewared.schema import Bool, Dict, Str
from middlewared.service import accepts, CallError, job, periodic, private, ConfigService, ValidationErrors
from middlewared.utils import filter_list, Popen
from middlewared.validators import Range

TRUECOMMAND_UPDATE_LOCK = asyncio.Lock()


class Status(enum.Enum):
    CONNECTED = 'CONNECTED'
    CONNECTING = 'CONNECTING'
    DISABLED = 'DISABLED'
    FAILED = 'FAILED'


class StatusReason(enum.Enum):
    CONNECTED = 'Truecommand service is connected.'
    CONNECTING = 'Pending Confirmation From iX Portal for Truecommand API Key.'
    DISABLED = 'Truecommand service is disabled.'
    FAILED = 'Truecommand API Key Disabled by iX Portal.'


class PortalResponseState(enum.Enum):
    ACTIVE = 'ACTIVE'
    FAILED = 'FAILED'  # This is not given by the API but is our internal check
    PENDING = 'PENDING'
    UNKNOWN = 'UNKNOWN'


class TrueCommandModel(sa.Model):
    __tablename__ = 'system_truecommand'

    id = sa.Column(sa.Integer(), primary_key=True)
    api_key = sa.Column(sa.String(128), default=None, nullable=True)
    api_key_state = sa.Column(sa.String(128), default='DISABLED', nullable=True)
    wg_public_key = sa.Column(sa.String(255), default=None, nullable=True)
    wg_private_key = sa.Column(sa.String(255), default=None, nullable=True)
    wg_address = sa.Column(sa.String(255), default=None, nullable=True)
    tc_public_key = sa.Column(sa.String(255), default=None, nullable=True)
    endpoint = sa.Column(sa.String(255), default=None, nullable=True)
    remote_address = sa.Column(sa.String(255), default=None, nullable=True)
    enabled = sa.Column(sa.Boolean(), default=False)


class TrueCommandService(ConfigService):

    POLLING_GAP_MINUTES = 5
    PORTAL_URI = 'https://portal.ixsystems.com/api'
    STATUS = Status.DISABLED

    class Config:
        service = 'truecommand'
        datastore = 'system.truecommand'
        datastore_extend = 'truecommand.tc_extend'

    @private
    async def tc_extend(self, config):
        for key in ('wg_public_key', 'wg_private_key', 'tc_public_key', 'endpoint', 'api_key_state'):
            config.pop(key)
        config.update({
            'status': self.STATUS.value,
            'status_reason': StatusReason.__members__[self.STATUS.value].value
        })
        return config

    @accepts(
        Dict(
            'truecommand_update',
            Bool('enabled'),
            Str('api_key', null=True, validators=[Range(min=16, max=16)]),
        )
    )
    async def do_update(self, data):
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
        with TRUECOMMAND_UPDATE_LOCK:
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

            if new['enabled']:
                if not old['wg_public_key'] or not old['wg_private_key']:
                    new.update(**(await self.generate_wg_keys()))

                if old['api_key'] != new['api_key']:
                    self.middleware.call_sync('truecommand.register_with_portal', new)
                    # Registration succeeded, we are good to poll now

            if old['api_key'] != new['api_key']:
                self.STATUS = Status.DISABLED
                new.update({
                    'remote_address': None,
                    'endpoint': None,
                    'tc_public_key': None,
                    'api_key_state': Status.DISABLED.value,
                })
                await self.dismiss_alerts()

            if not new['enabled']:
                self.STATUS = Status.DISABLED

            # We are going to stop truecommand service with this update anyways as only 2 possible actions
            # can happen on update
            # 1) Service enabled/disabled
            # 2) Api Key changed
            await self.middleware.call_hook('truecommand.service.events', data={'action': 'STOP'})

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                old['id'],
                new
            )

            if new['enabled'] and any(old[k] != new[k] for k in ('api_key', 'enabled')):
                # We are going to start polling here
                await self.middleware.call('truecommand.poll_api_for_status')

            return await self.config()

    @private
    async def dismiss_alerts(self):
        for klass in ('TruecommandConnectionDisabled', 'TruecommandConnectionPending'):
            await self.middleware.call('alert.oneshot_delete', klass)

    @private
    @job(lock='poll_ix_portal_api_truecommand')
    async def poll_api_for_status(self, job):
        self.STATUS = Status.CONNECTING

        config = await self.middleware.call('datastore.config', self._config.datastore)
        while config['enabled']:
            try:
                status = await self.middleware.call('truecommand.poll_once', config)
            except Exception as e:
                status = {
                    'error': f'Failed to poll for status of API Key: {e}',
                    'state': PortalResponseState.FAILED,
                }

            if status['state'] == PortalResponseState.ACTIVE:
                await self.middleware.call(
                    'datastore.update',
                    self._config.datastore,
                    config['id'], {
                        'tc_public_key': status['tc_pubkey'],
                        'remote_address': status['wg_netaddr'],
                        'endpoint': status['wg_accesspoint'],
                        'api_key_state': Status.CONNECTED.value,
                    }
                )
                self.STATUS = Status.CONNECTED
                await self.dismiss_alerts()
                await self.middleware.call_hook('truecommand.service.events', data={'action': 'START'})
                break

            elif status['state'] == PortalResponseState.UNKNOWN:
                # We are not going to poll anymore as this definitely means
                # that iX Portal has deactivated this key and is not going to work with this
                # api key again
                # Clear connection pending alert if any
                await self.middleware.call('alert.oneshot_delete', 'TruecommandConnectionPending')
                await self.middleware.call(
                    'alert.oneshot_create', 'TruecommandConnectionDisabled', {
                        'error': status['error'],
                    }
                )
                self.middleware.logger.debug('iX Portal has disabled API Key: %s', status['error'])
                self.STATUS = Status.FAILED
                break

            elif not filter_list(
                await self.middleware.call('alert.list'), [
                    ['klass', '=', 'TruecommandConnectionPending'], ['args.error', '=', status['error']]
                ]
            ):
                await self.middleware.call(
                    'alert.oneshot_create', 'TruecommandConnectionPending', {
                        'error': status['error']
                    }
                )
                self.middleware.logger.debug(
                    'Pending Confirmation From iX Portal for Truecommand API Key: %s', status['error']
                )

            await asyncio.sleep(self.POLLING_GAP_MINUTES * 60)
            config = await self.middleware.call_sync('datastore.config', self._config.datastore)

    @private
    def poll_once(self, config):
        # If this function returns state = True, we are going to assume we are good and no more polling
        # is required, for false, we will continue the loop
        error_msg = None
        try:
            response = requests.post(
                self.PORTAL_URI, json={
                    'action': 'status-wireguard-key',
                    'apikey': config['api_key'],
                    'nas_pubkey': config['wg_public_key'],
                }, timeout=15
            )
        except requests.exceptions.Timeout:
            error_msg = 'Failed to poll for status of API Key in 15 seconds'
        else:
            try:
                response.raise_for_status()
            except requests.HTTPError as e:
                error_msg = f'Failed to poll for status of API Key: {e}'
            else:
                response = response.json()
                if 'state' not in response or response['state'].upper() not in PortalResponseState.__members__.values():
                    error_msg = 'Malformed response returned by iX Portal'

        if error_msg:
            # Either request failed or we got bad response
            response = {'state': PortalResponseState.FAILED.value}

        status_dict = {'error': error_msg, 'state': PortalResponseState(response.pop('state').upper())}

        # There are 3 states here which the api can give us - active, pending, unknown
        if response['state'] == PortalResponseState.ACTIVE:
            if any(k not in response for k in ('tc_pubkey', 'wg_netaddr', 'wg_accesspoint', 'nas_pubkey')):
                status_dict.update({
                    'state': PortalResponseState.FAILED,
                    'error': f'Malformed ACTIVE response received by iX Portal with {", ".join(response)} keys'
                })
            elif response['nas_pubkey'] != config['wg_public_key']:
                status_dict.update({
                    'state': PortalResponseState.FAILED,
                    'error': f'Public key "{response["nas_pubkey"]}" of TN from iX Portal does not '
                             f'match TN Config public key "{config["wg_public_key"]}".'
                })
            else:
                status_dict.update(response)
        elif response['state'] == PortalResponseState.UNKNOWN:
            status_dict['error'] = response.get('details') or 'API Key has been disabled by the iX Portal'
        elif response['state'] == PortalResponseState.PENDING:
            # This is pending now
            status_dict['error'] = 'Waiting for iX Portal to confirm API Key'

        return status_dict

    @private
    def register_with_portal(self, config):
        # We are going to register the api key with the portal and if it fails,
        # We are going to fail hard and fast without saving any information in the database if we fail to
        # register for whatever reason.
        sys_info = self.middleware.call_sync('system.info')
        try:
            response = requests.post(
                self.PORTAL_URI, json={
                    'action': 'add-truecommand-wg-key',
                    'apikey': config['api_key'],
                    'nas_pubkey': config['wg_public_key'],
                    'hostname': sys_info['hostname'],
                    'sysversion': sys_info['version'],
                }, timeout=15
            )
        except requests.exceptions.Timeout:
            raise CallError('Failed to register api key with iX portal in 15 seconds.')
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            raise CallError(f'Failed to register API Key with portal ({response.status_code} Error Code): {e}')
        else:
            response = response.json()

        if 'status' not in response or str(response['status']).lower() not in ('pending', 'duplicate', 'denied'):
            raise CallError(f'Unknown response got from iX portal API: {response}')
        elif response['status'].lower() == 'duplicate':
            raise CallError(f'This API Key has already been registered with iX Portal.')
        elif response['status'].lower() == 'denied':
            # Discussed with Ken and he said it's safe to assume that if we get denied
            # we should assume the API Key is invalid
            raise CallError(f'The provided API Key is invalid.')

    @private
    async def generate_wg_keys(self):
        cp = await Popen(['wg', 'genkey'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        private_key, stderr = await cp.communicate()
        if cp.returncode:
            raise CallError(
                f'Failed to generate key for wireguard with exit code ({cp.returncode}): {stderr.decode()}'
            )

        cp = await Popen(
            ['wg', 'pubkey'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        public_key, stderr = await cp.communicate(input=private_key)
        if cp.returncode:
            raise CallError(
                f'Failed to generate public key for wireguard with exit code ({cp.returncode}): {stderr.decode()}'
            )

        return {'wg_public_key': public_key.decode().strip(), 'wg_private_key': private_key.decode().strip()}

    @private
    async def start_truecommand_service(self):
        config = await self.config()
        if config['enabled'] and Status(config['status']) == Status.CONNECTED and all(
            config[k] for k in ('wg_private_key', 'remote_address', 'endpoint', 'tc_public_key')
        ):
            await self.middleware.call('service.start', 'truecommand')


async def _event_system(middleware, event_type, args):
    if args['id'] == 'ready':
        await middleware.call('truecommand.start_truecommand_service')
    elif args['id'] == 'shutdown' and await middleware.call('service.started', 'truecommand'):
        # Stop wireguard here please if we have it enabled
        await middleware.call('service.stop', 'truecommand')


async def truecommand_service_hook(middleware, data):
    if data['action'] == 'START':
        await middleware.call('truecommand.start_truecommand_service')
    elif data['action'] == 'STOP':
        await middleware.call('service.stop', 'truecommand')


async def setup(middleware):
    tc_config = await middleware.call('datastore.config', 'system.truecommand')
    if tc_config['api_key_state'] == 'CONNECTED':
        TrueCommandService.STATUS = Status.CONNECTED

    middleware.event_subscribe('system', _event_system)
    if await middleware.call('system.ready') and not await middleware.call('service.started', 'truecommand'):
        asyncio.ensure_future(middleware.call('truecommand.start_truecommand_service'))
    middleware.register_hook('truecommand.service.events', truecommand_service_hook)
