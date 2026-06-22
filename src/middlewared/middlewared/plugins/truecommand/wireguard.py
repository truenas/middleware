from __future__ import annotations

import asyncio
import re
import time

from middlewared.alert.source.truecommand import TruecommandConnectionHealthAlert
from middlewared.api.current import TruecommandStatus
from middlewared.service import CallError, ServiceContext
from middlewared.utils import run

from .state import dismiss_alerts, set_status
from .utils import WIREGUARD_INTERFACE_NAME

HEALTH_CHECK_SECONDS = 1800
WIREGUARD_HEALTH_RE = re.compile(r'=\s*(.*)')


async def generate_wg_keys() -> dict[str, str]:
    cp = await run(['wg', 'genkey'], check=False)
    private_key = cp.stdout
    if cp.returncode:
        raise CallError(
            f'Failed to generate key for wireguard with exit code ({cp.returncode}): {cp.stderr.decode()}'
        )

    cp = await run(['wg', 'pubkey'], input=private_key, check=False)
    public_key = cp.stdout
    if cp.returncode:
        raise CallError(
            f'Failed to generate public key for wireguard with exit code ({cp.returncode}): {cp.stderr.decode()}'
        )

    return {'wg_public_key': public_key.decode().strip(), 'wg_private_key': private_key.decode().strip()}


async def health_check(context: ServiceContext) -> None:
    # The purpose of this method is to ensure that the wireguard connection
    # is active. If wireguard service is running, we want to make sure that the last
    # handshake we have had was under 30 minutes.
    if not await context.middleware.call('failover.is_single_master_node') or TruecommandStatus(
        (await context.middleware.call('datastore.config', 'system.truecommand'))['api_key_state']
    ) != TruecommandStatus.CONNECTED:
        await context.call2(context.s.alert.oneshot_delete, 'TruecommandConnectionHealth', None)
        return

    if not await wireguard_connection_health(context):
        # Stop wireguard if it's running and start polling the api to see what's up
        await set_status(context, TruecommandStatus.CONNECTING.value)
        await stop_truecommand_service(context)
        await context.call2(context.s.alert.oneshot_create, TruecommandConnectionHealthAlert())
        await context.call2(context.s.truecommand.poll_api_for_status)
    else:
        # Mark the connection as connected - we do this for just in case user never called
        # truecommand.config and is in WAITING state right now assuming that an event will be
        # raised when TC finally connects
        await set_status(context, TruecommandStatus.CONNECTED.value)
        await dismiss_alerts(context, False, True)


async def wireguard_connection_health(context: ServiceContext) -> bool:
    """
    Returns true if we are connected and wireguard connection has have had a handshake within last
    HEALTH_CHECK_SECONDS
    """
    health_error = not (await context.middleware.call('service.started', 'truecommand'))
    if not health_error:
        cp = await run(['wg', 'show', WIREGUARD_INTERFACE_NAME, 'latest-handshakes'], encoding='utf8', check=False)
        if cp.returncode:
            health_error = True
        else:
            matches = WIREGUARD_HEALTH_RE.findall(cp.stdout)
            timestamp = matches[0].strip() if matches else ''
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
                config = await context.middleware.call('datastore.config', 'system.truecommand')
                ping_cp = await run([
                    'ping', '-w', '5', '-q', str(config['remote_address'].split('/', 1)[0])
                ], check=False)
                if ping_cp.returncode:
                    # We have return code of 0 if we heard at least one response from the host
                    health_error = True
    return not health_error


async def start_truecommand_service(context: ServiceContext) -> None:
    config = await context.middleware.call('datastore.config', 'system.truecommand')
    if config['enabled'] and await context.middleware.call('failover.is_single_master_node'):
        if TruecommandStatus(config['api_key_state']) == TruecommandStatus.CONNECTED and all(
            config[k] for k in ('wg_private_key', 'remote_address', 'endpoint', 'tc_public_key', 'wg_address')
        ):
            await (await context.middleware.call(
                'service.control', 'START', 'truecommand', {'ha_propagate': False},
            )).wait(raise_error=True)
            await (await context.middleware.call(
                'service.control', 'RELOAD', 'http', {'ha_propagate': False},
            )).wait(raise_error=True)
            asyncio.get_event_loop().call_later(
                30,  # 30 seconds is enough time to initiate a health check to see if the connection is alive
                lambda: context.create_task(context.call2(context.s.truecommand.health_check)),
            )
        else:
            # start polling iX Portal to see what's up and why we don't have these values set
            # This can happen in instances where system was polling and then was rebooted,
            # So we should continue polling in this case
            await context.call2(context.s.truecommand.poll_api_for_status)


async def stop_truecommand_service(context: ServiceContext) -> None:
    await (await context.middleware.call('service.control', 'RELOAD', 'http')).wait(raise_error=True)
    if await context.middleware.call('service.started', 'truecommand'):
        await (await context.middleware.call('service.control', 'STOP', 'truecommand')).wait(raise_error=True)
