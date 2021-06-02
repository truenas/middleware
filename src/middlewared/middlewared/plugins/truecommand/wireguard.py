import re
import subprocess
import time

from middlewared.schema import Bool, Dict, IPAddr, returns, Str
from middlewared.service import accepts, CallError, no_auth_required, periodic, pass_app, private, Service, throttle
from middlewared.utils import osc, Popen, run

from .enums import Status

HEALTH_CHECK_SECONDS = 1800
WIREGUARD_HEALTH_RE = re.compile(r'=\s*(.*)')


def throttle_condition(middleware, app, *args, **kwargs):
    return app is None or (app and app.authenticated), None


class TruecommandService(Service):

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
    @periodic(HEALTH_CHECK_SECONDS, run_on_start=False)
    async def health_check(self):
        # The purpose of this method is to ensure that the wireguard connection
        # is active. If wireguard service is running, we want to make sure that the last
        # handshake we have had was under 30 minutes.
        if Status(
            (await self.middleware.call('datastore.config', 'system.truecommand'))['api_key_state']
        ) != Status.CONNECTED:
            await self.middleware.call('alert.oneshot_delete', 'TruecommandConnectionHealth', None)
            return

        if not await self.wireguard_connection_health():
            # Stop wireguard if it's running and start polling the api to see what's up
            await self.middleware.call('truecommand.set_status', Status.CONNECTING.value)
            await self.stop_truecommand_service()
            await self.middleware.call('alert.oneshot_create', 'TruecommandConnectionHealth', None)
            await self.middleware.call('truecommand.poll_api_for_status')
        else:
            # Mark the connection as connected - we do this for just in case user never called
            # truecommand.config and is in WAITING state right now assuming that an event will be
            # raised when TC finally connects
            await self.middleware.call('truecommand.set_status', Status.CONNECTED.value)
            await self.middleware.call('alert.oneshot_delete', 'TruecommandConnectionHealth', None)

    @private
    async def wireguard_connection_health(self):
        """
        Returns true if we are connected and wireguard connection has have had a handshake within last
        HEALTH_CHECK_SECONDS
        """
        health_error = not (await self.middleware.call('service.started', 'truecommand'))
        if not health_error:
            cp = await run(['wg', 'show', 'wg0', 'latest-handshakes'], encoding='utf8', check=False)
            if cp.returncode:
                health_error = True
            else:
                timestamp = WIREGUARD_HEALTH_RE.findall(cp.stdout)
                if not timestamp:
                    health_error = True
                else:
                    timestamp = timestamp[0].strip()
                if timestamp == '0' or not timestamp.isdigit() or (
                    int(time.time()) - int(timestamp)
                ) > HEALTH_CHECK_SECONDS:
                    # We never established handshake with TC if timestamp is 0, otherwise it's been more
                    # then 30 minutes, error out please
                    health_error = True
                else:
                    # It's possible that IP of TC changed and we just need to get up to speed with the
                    # new IP. So if we have a correct handshake, we should ping the TC IP to see if it's
                    # still reachable
                    config = await self.middleware.call('datastore.config', 'system.truecommand')
                    cp = await run(
                        [
                            'ping', '-t' if osc.IS_FREEBSD else '-w', '5', '-q',
                            str(config['remote_address'].split('/', 1)[0])
                        ], check=False
                    )
                    if cp.returncode:
                        # We have return code of 0 if we heard at least one response from the host
                        health_error = True
        return not health_error

    @no_auth_required
    @throttle(seconds=2, condition=throttle_condition)
    @accepts()
    @returns(Dict(
        'truecommand_connected',
        Bool('connected', required=True),
        IPAddr('truecommand_ip', null=True, required=True),
        Str('truecommand_url', null=True, required=True),
        Str('status', required=True),
        Str('status_reason', required=True),
    ))
    @pass_app()
    async def connected(self, app):
        """
        Returns information which shows if system has an authenticated api key
        and has initiated a VPN connection with TrueCommand.
        """
        tc_config = await self.middleware.call('truecommand.config')
        connected = Status(tc_config['status']) == Status.CONNECTED
        return {
            'connected': connected,
            'truecommand_ip': tc_config['remote_ip_address'] if connected else None,
            'truecommand_url': tc_config['remote_url'] if connected else None,
            'status': tc_config['status'],
            'status_reason': tc_config['status_reason'],
        }

    @private
    async def start_truecommand_service(self):
        config = await self.middleware.call('datastore.config', 'system.truecommand')
        if config['enabled']:
            if Status(config['api_key_state']) == Status.CONNECTED and all(
                config[k] for k in ('wg_private_key', 'remote_address', 'endpoint', 'tc_public_key', 'wg_address')
            ):
                await self.middleware.call('service.start', 'truecommand')
                await self.middleware.call('service.reload', 'http')
            else:
                # start polling iX Portal to see what's up and why we don't have these values set
                # This can happen in instances where system was polling and then was rebooted,
                # So we should continue polling in this case
                await self.middleware.call('truecommand.poll_api_for_status')

    @private
    async def stop_truecommand_service(self):
        await self.middleware.call('service.reload', 'http')
        if await self.middleware.call('service.started', 'truecommand'):
            await self.middleware.call('service.stop', 'truecommand')
