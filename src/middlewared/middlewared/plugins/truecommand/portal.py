import asyncio
import socket

from middlewared.service import CallError, job, private, Service

from .connection import TruecommandAPIMixin
from .enums import PortalResponseState, Status


class TruecommandService(Service, TruecommandAPIMixin):

    POLLING_GAP_MINUTES = 5

    @private
    @job(lock='poll_ix_portal_api_truecommand')
    async def poll_api_for_status(self, job):
        await self.middleware.call('truecommand.set_status', Status.CONNECTING.value)
        config = await self.middleware.call('datastore.config', 'system.truecommand')

        while config['enabled']:
            try:
                status = await self.poll_once(config)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                status = {
                    'error': f'Failed to poll for status of API Key: {e}',
                    'state': PortalResponseState.FAILED,
                }

            if status['state'] == PortalResponseState.ACTIVE:
                await self.middleware.call(
                    'datastore.update',
                    'system.truecommand',
                    config['id'], {
                        'tc_public_key': status['tc_pubkey'],
                        'wg_address': status['wg_netaddr'],
                        'remote_address': status['tc_wg_netaddr'],
                        'endpoint': status['wg_accesspoint'],
                        'api_key_state': Status.CONNECTED.value,
                    }
                )
                self.middleware.send_event(
                    'truecommand.config', 'CHANGED', fields=(await self.middleware.call('truecommand.config'))
                )
                await self.middleware.call('truecommand.dismiss_alerts')
                await self.middleware.call('truecommand.start_truecommand_service')
                break

            elif status['state'] == PortalResponseState.UNKNOWN:
                # We are not going to poll anymore as this definitely means
                # that iX Portal has deactivated this key and is not going to work with this
                # api key again
                # Clear TC pending alerts if any, what only matters now is that key has been disabled by portal
                await self.middleware.call('truecommand.dismiss_alerts', True)
                await self.middleware.call(
                    'alert.oneshot_create', 'TruecommandConnectionDisabled', {
                        'error': status['error'],
                    }
                )
                self.middleware.logger.debug('iX Portal has disabled API Key: %s', status['error'])
                await self.middleware.call('truecommand.set_status', Status.FAILED.value)
                # Let's remove TC's address if they are there and if the api key state was enabled
                # Also let's make sure truecommand service is not running, it shouldn't be but still enforce it
                await self.middleware.call(
                    'datastore.update',
                    'system.truecommand',
                    config['id'], {
                        **{k: None for k in ('tc_public_key', 'remote_address', 'endpoint', 'wg_address')},
                        'api_key_state': Status.FAILED.value,
                    }
                )
                self.middleware.send_event(
                    'truecommand.config', 'CHANGED', fields=(await self.middleware.call('truecommand.config'))
                )
                await self.middleware.call('truecommand.stop_truecommand_service')
                break

            else:
                await self.middleware.call(
                    'alert.oneshot_create', 'TruecommandConnectionPending', {
                        'error': status['error']
                    }
                )
                self.middleware.logger.debug(
                    'Pending Confirmation From iX Portal for Truecommand API Key: %s', status['error']
                )

            await asyncio.sleep(self.POLLING_GAP_MINUTES * 60)
            config = await self.middleware.call('datastore.config', 'system.truecommand')

    @private
    async def poll_once(self, config):
        response = await self._post_call(payload={
            'action': 'status-wireguard-key',
            'apikey': config['api_key'],
            'nas_pubkey': config['wg_public_key'],
        })
        if response['error']:
            response.update({
                'state': PortalResponseState.FAILED.value,
                'error': f'Failed to poll for status of API Key: {response["error"]}'
            })
        else:
            response = response['response']
            if 'state' not in response or response['state'].upper() not in PortalResponseState.__members__:
                response.update({
                    'state': PortalResponseState.FAILED.value,
                    'error': 'Malformed response returned by iX Portal'
                })
            else:
                response['error'] = None

        status_dict = {'error': response.pop('error'), 'state': PortalResponseState(response.pop('state').upper())}

        # There are 3 states here which the api can give us - active, pending, unknown
        if status_dict['state'] == PortalResponseState.ACTIVE:
            if any(
                k not in response for k in
                ('tc_pubkey', 'wg_netaddr', 'wg_accesspoint', 'nas_pubkey', 'tc_wg_netaddr')
            ):
                status_dict.update({
                    'state': PortalResponseState.FAILED,
                    'error': f'Malformed ACTIVE response received by iX Portal with {", ".join(response)} keys'
                })
            elif response['nas_pubkey'] != config['wg_public_key']:
                status_dict.update({
                    'state': PortalResponseState.FAILED,
                    'error': f'Public key "{response["nas_pubkey"]}" of TrueNAS from iX Portal does not '
                             f'match TrueNAS Config public key "{config["wg_public_key"]}".'
                })
            else:
                status_dict.update(response)
        elif status_dict['state'] == PortalResponseState.UNKNOWN:
            status_dict['error'] = response.get('details') or 'API Key has been disabled by the iX Portal'
        elif status_dict['state'] == PortalResponseState.PENDING:
            # This is pending now
            status_dict['error'] = 'Waiting for iX Portal to confirm API Key'

        return status_dict

    @private
    async def register_with_portal(self, config):
        # We are going to register the api key with the portal and if it fails,
        # We are going to fail hard and fast without saving any information in the database if we fail to
        # register for whatever reason.
        response = await self._post_call(payload={
            'action': 'add-truecommand-wg-key',
            'apikey': config['api_key'],
            'nas_pubkey': config['wg_public_key'],
            'hostname': socket.gethostname(),
            'sysversion': await self.middleware.call('system.version'),
        })

        if response['error']:
            raise CallError(f'Failed to register API Key with portal: {response["error"]}')
        else:
            response = response['response']

        if 'state' not in response or str(response['state']).lower() not in ('pending', 'duplicate', 'denied'):
            raise CallError(f'Unknown response got from iX portal API: {response}')
        elif response['state'].lower() == 'denied':
            # Discussed with Ken and he said it's safe to assume that if we get denied
            # we should assume the API Key is invalid
            raise CallError('The provided API Key is invalid.')
