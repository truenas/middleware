import re
import subprocess
import time

from middlewared.service import CallError, periodic, private, Service
from middlewared.utils import Popen, run

from .enums import Status

WIREGUARD_HEALTH_RE = re.compile(r'=\s*(.*)')


class TruecommandService(Service):

    HEALTH_CHECK_SECONDS = 1800

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
    @periodic(1800, run_on_start=False)
    async def health_check(self):
        # The purpose of this method is to ensure that the wireguard connection
        # is active. If wireguard service is running, we want to make sure that the last
        # handshake we have had was under 30 minutes.
        if Status((await self.middleware.call('truecommand.config'))['status']) != Status.CONNECTED:
            return

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
                ) > self.HEALTH_CHECK_SECONDS:
                    # We never established handshake with TC if timestamp is 0, otherwise it's been more
                    # then 30 minutes, error out please
                    health_error = True

        if health_error:
            # Stop wireguard if it's running and start polling the api to see what's up
            await self.stop_truecommand_service()
            await self.middleware.call('alert.oneshot_create', 'TruecommandConnectionHealth', None)
            await self.middleware.call('truecommand.poll_api_for_status')
        else:
            await self.middleware.call('alert.oneshot_delete', 'TruecommandConnectionHealth', None)

    @private
    async def start_truecommand_service(self):
        config = await self.middleware.call('datastore.config', 'system.truecommand')
        if config['enabled']:
            if Status((await self.middleware.call('truecommand.config'))['status']) == Status.CONNECTED and all(
                config[k] for k in ('wg_private_key', 'remote_address', 'endpoint', 'tc_public_key', 'wg_address')
            ):
                await self.middleware.call('service.start', 'truecommand')
            else:
                # start polling iX Portal to see what's up and why we don't have these values set
                # This can happen in instances where system was polling and then was rebooted,
                # So we should continue polling in this case
                await self.middleware.call('truecommand.poll_api_for_status')

    @private
    async def stop_truecommand_service(self):
        if await self.middleware.call('service.started', 'truecommand'):
            await self.middleware.call('service.stop', 'truecommand')
