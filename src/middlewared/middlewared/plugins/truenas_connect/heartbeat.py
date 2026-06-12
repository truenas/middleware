from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any

from truenas_connect_utils.config import get_account_id_and_system_id
from truenas_connect_utils.urls import get_heartbeat_url

from middlewared.alert.source.truenas_connect import TNCHeartbeatConnectionFailureAlert
from middlewared.service import CallError, ServiceContext
from middlewared.utils.disks_.disk_class import iterate_disks
from middlewared.utils.version import parse_version_string

from .internal import config_internal, handle_tnc_deregistration
from .request import Mode, auth_headers, tnc_request
from .utils import (
    CONFIGURED_TNC_STATES,
    HEARTBEAT_INTERVAL,
    calculate_sleep,
    decode_and_validate_token,
)

logger = logging.getLogger('truenas_connect')


async def _heartbeat_request(
    context: ServiceContext,
    url: str,
    mode: Mode,
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    config = await config_internal(context)
    return await tnc_request(
        url, mode, payload=payload, headers=auth_headers(config), **kwargs,
    )


async def _build_payload(
    context: ServiceContext, disk_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    stats = await context.middleware.call('reporting.realtime.stats', disk_mapping)
    # We would like to add app/vm stats here as well now
    apps = await context.call2(context.s.app.query)
    vms = await context.call2(context.s.vm.query)
    stats.update({
        'apps': {
            'total': len(apps),
            'running': len([app for app in apps if app.state == 'RUNNING']),
        },
        'vms': {
            'total': len(vms),
            'running': len([vm for vm in vms if vm.status.state == 'RUNNING']),
        },
    })
    return {
        'alerts': await context.call2(context.s.alert.list),
        'stats': stats,
    }


async def heartbeat_start_impl(context: ServiceContext) -> None:
    logger.debug('TNC Heartbeat: Starting heartbeat service')
    tnc_config = await config_internal(context)
    creds = get_account_id_and_system_id(tnc_config)
    if tnc_config['status'] not in CONFIGURED_TNC_STATES or creds is None:
        raise CallError('TrueNAS Connect is not configured properly')

    heartbeat_url = get_heartbeat_url(tnc_config).format(
        system_id=creds['system_id'],
        version=parse_version_string(await context.middleware.call('system.version_short')),
    )
    disk_mapping = {i.name: i.identifier for i in iterate_disks()}
    while tnc_config['status'] in CONFIGURED_TNC_STATES:
        sleep_error = False
        resp = await _heartbeat_request(
            context, heartbeat_url, 'post', await _build_payload(context, disk_mapping), get_response=False,
        )
        if resp['error'] is not None and resp['status_code'] is None:
            logger.debug('TNC Heartbeat: Failed to connect to heart beat service (%s)', resp['error'])
            sleep_error = True
        else:
            match resp['status_code']:
                case 200 | 202:
                    # Just keeping this here for valid codes, we don't need to do anything
                    pass
                case 205:
                    if (new_token := resp['headers'].get('X-New-Token')) is not None:
                        logger.debug('TNC Heartbeat: Received new token')

                        try:
                            decoded_token = decode_and_validate_token(new_token)
                        except ValueError as e:
                            logger.error('TNC Heartbeat: Failed to validate received token: %s', e)
                        else:
                            await context.middleware.call(
                                'datastore.update',
                                'truenas_connect',
                                tnc_config['id'],
                                {
                                    'jwt_token': new_token,
                                    'registration_details': decoded_token,
                                },
                            )
                            tnc_config.update({
                                'jwt_token': new_token,
                                'registration_details': decoded_token,
                            })
                    else:
                        logger.warning('TNC Heartbeat: Received 205 status but no X-New-Token header')
                case 400:
                    logger.debug('TNC Heartbeat: Received 400')
                    sleep_error = True
                case 401:
                    logger.debug('TNC Heartbeat: Received 401, unsetting TNC')
                    await handle_tnc_deregistration(context)
                    return
                case 500:
                    logger.debug('TNC Heartbeat: Received 500')
                    sleep_error = True
                case _:
                    logger.debug('TNC Heartbeat: Received unknown status code %r', resp['status_code'])
                    sleep_error = True

        if sleep_error:
            if tnc_config['last_heartbeat_failure_datetime'] is None:
                last_failure = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
                await context.middleware.call('datastore.update', 'truenas_connect', tnc_config['id'], {
                    'last_heartbeat_failure_datetime': last_failure,
                })
            else:
                last_failure = tnc_config['last_heartbeat_failure_datetime']

            sleep_secs = calculate_sleep(last_failure, HEARTBEAT_INTERVAL)
            if sleep_secs is None:
                # This means that either we have a time mismatch or it's been 48 hours and we have
                # not been able to establish contact with TNC, so an alert should be raised
                logger.debug(
                    'TNC Heartbeat: Unable to calculate sleep time, raising alert as it has likely been 48 hours '
                    'since the last successful heartbeat (last failure: %s)', last_failure,
                )
                await context.call2(context.s.alert.oneshot_create, TNCHeartbeatConnectionFailureAlert())
                break
            else:
                logger.debug(
                    'TNC Heartbeat: Sleeping for %d seconds based off last failure (%s)', sleep_secs, last_failure
                )
                await asyncio.sleep(sleep_secs)
        else:
            if tnc_config['last_heartbeat_failure_datetime'] is not None:
                await context.middleware.call('datastore.update', 'truenas_connect', tnc_config['id'], {
                    'last_heartbeat_failure_datetime': None,
                })
                logger.debug('TNC Heartbeat: Resetting last heartbeat failure datetime')

            await context.call2(context.s.alert.oneshot_delete, 'TNCHeartbeatConnectionFailure')
            await asyncio.sleep(HEARTBEAT_INTERVAL)

        tnc_config = await config_internal(context)
