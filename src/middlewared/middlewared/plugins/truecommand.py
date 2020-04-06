import asyncio
import enum
import requests
import subprocess

import middlewared.sqlalchemy as sa

from middlewared.schema import Bool, Dict, Str
from middlewared.service import accepts, CallError, private, ConfigService, ValidationErrors
from middlewared.utils import Popen
from middlewared.validators import Range

TRUECOMMAND_FLAG_POLL_LOCK = asyncio.Lock()
TRUECOMMAND_UPDATE_LOCK = asyncio.Lock()


class ApiKeyStates(enum.Enum):
    ACTIVE = 'ACTIVE'
    DEACTIVATED = 'DEACTIVATED'


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
    POLLING_FLAG = False
    POLLING_ACTIVE = False
    PORTAL_URI = 'https://portal.ixsystems.com/api'

    class Config:
        service = 'truecommand'
        datastore = 'system.truecommand'
        datastore_extend = 'truecommand.tc_extend'

    @private
    async def tc_extend(self, config):
        for key in ('wg_public_key', 'wg_private_key', 'tc_public_key', 'endpoint'):
            config.pop(key)
        return config

    @accepts(
        Dict(
            'truecommand_update',
            Bool('enabled'),
            Str('api_key', null=True, validators=[Range(min=16, max=16)]),
        )
    )
    async def do_update(self, data):
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

            with TRUECOMMAND_FLAG_POLL_LOCK:
                self.POLLING_FLAG = False

            while self.POLLING_ACTIVE:
                await asyncio.sleep(1)

            if new['enabled']:
                if not old['wg_public_key'] or not old['wg_private_key']:
                    new.update(**(await self.generate_wg_keys()))

                if old['api_key'] != new['api_key']:
                    self.middleware.call_sync('truecommand.register_with_portal', new)
                    # Registration succeeded, we are good to poll now

            if old['api_key'] != new['api_key']:
                new['api_key_state'] = ApiKeyStates.DEACTIVATED.value

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                old['id'],
                new
            )

            if new['enabled'] and any(old[k] != new[k] for k in ('api_key', 'enabled')):
                # We are going to start polling here
                asyncio.ensure_future(self.poll_api_for_status())

            return await self.config()

    @private
    async def poll_api_for_status(self):
        with TRUECOMMAND_FLAG_POLL_LOCK:
            self.POLLING_ACTIVE = True
            self.POLLING_FLAG = True

        try:
            config = await self.middleware.call('datastore.config', self._config.datastore)
            while config['enabled'] and self.POLLING_FLAG:
                try:
                    status = await self.middleware.call('truecommand.poll_once', config)
                except Exception as e:
                    status = {'error': f'Failed to poll for status of API Key: {e}', 'continue_loop': True}

                if not status['continue_loop'] and status['state'].lower() == 'active':
                    await self.middleware.call(
                        'datastore.update',
                        self._config.datastore,
                        config['id'], {
                            'tc_public_key': status['tc_pubkey'],
                            'remote_address': status['wg_netaddr'],
                            'endpoint': status['wg_accesspoint'],
                            'api_key_state': ApiKeyStates.ACTIVE.value,
                        }
                    )
                    break

                if status['error']:
                    # TODO: Raise an alert please
                    pass

                await asyncio.sleep(self.POLLING_GAP_MINUTES * 60)
                config = await self.middleware.call_sync('datastore.config', self._config.datastore)
        finally:
            with TRUECOMMAND_FLAG_POLL_LOCK:
                self.POLLING_ACTIVE = self.POLLING_FLAG = False

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
                if 'state' not in response or response['state'] not in ('active', 'pending', 'unknown'):
                    error_msg = 'Malformed response returned by iX Portal'

        status_dict = {'error': error_msg, 'continue_loop': True}
        if not error_msg:
            # There are 3 states here which the api can give us - active, pending, unknown
            if response['state'].lower() == 'active':
                if any(k not in response for k in ('tc_pubkey', 'wg_netaddr', 'wg_accesspoint', 'nas_pubkey')):
                    status_dict['error'] = 'Malformed ACTIVE response received by iX Portal ' \
                                           f'with {", ".join(response)} keys'
                elif response['nas_pubkey'] != config['wg_public_key']:
                    status_dict['error'] = f'Public key "{response["nas_pubkey"]}" of TN from iX Portal ' \
                                           f'does not match TN Config public key "{config["wg_public_key"]}".'
                else:
                    status_dict.update({**response, 'continue_loop': False})
            elif response['state'].lower() == 'unknown':
                status_dict['error'] = response.get('details') or 'API Key has been disabled by the iX Portal'

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
