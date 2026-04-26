from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any

from truenas_connect_utils.status import Status
from truenas_connect_utils.urls import get_registration_finalization_uri

from middlewared.service import ServiceContext

from .internal import config_internal, set_status
from .request import tnc_request
from .utils import calculate_sleep, CLAIM_TOKEN_CACHE_KEY, decode_and_validate_token


logger = logging.getLogger('truenas_connect')

BACKOFF_BASE_SLEEP = 5


async def status_update(
    context: ServiceContext, status: Status, log_message: str | None = None,
) -> None:
    await set_status(context, status.name)
    if log_message:
        logger.error(log_message)


async def finalize_registration_impl(context: ServiceContext) -> None:
    logger.debug('Starting TNC registration finalization')
    start_time = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    config = await context.call2(context.s.tn_connect.config)
    system_id = await context.middleware.call('system.global.id')
    try_num = 1
    while config.status == Status.REGISTRATION_FINALIZATION_WAITING.name:
        try:
            claim_token = await context.middleware.call('cache.get', CLAIM_TOKEN_CACHE_KEY)
        except KeyError:
            # We have hit timeout
            # TODO: Add alerts
            logger.debug('TNC claim token has expired')
            await status_update(context, Status.REGISTRATION_FINALIZATION_TIMEOUT)
            return

        try:
            logger.debug('Attempt %r: Polling for TNC registration finalization', try_num)
            # _poll_once needs the raw config dict (with jwt_token etc) for URL composition
            tnc_config = await config_internal(context)
            poll_status = await _poll_once(claim_token, system_id, tnc_config)
        except asyncio.CancelledError:
            await status_update(
                context,
                Status.REGISTRATION_FINALIZATION_TIMEOUT,
                'TNC registration finalization polling has been cancelled',
            )
            raise
        except Exception as e:
            logger.debug('TNC registration has not been finalized yet: %r', str(e))
            poll_status = {'error': str(e)}
        finally:
            try_num += 1

        if poll_status['error'] is None:
            # We have got the key now and the registration has been finalized
            if 'token' not in poll_status['response']:
                logger.error(
                    'Registration finalization failed for TNC as token not found in response: %r',
                    poll_status['response']
                )
                await status_update(context, Status.REGISTRATION_FINALIZATION_FAILED)
            else:
                token = poll_status['response']['token']
                try:
                    decoded_token = decode_and_validate_token(token)
                except ValueError as e:
                    logger.error('Failed to validate received token: %s', e)
                    await status_update(context, Status.REGISTRATION_FINALIZATION_FAILED)
                    return

                await context.middleware.call(
                    'datastore.update', 'truenas_connect', config.id, {
                        'jwt_token': token,
                        'registration_details': decoded_token,
                    }
                )
                await status_update(context, Status.CERT_GENERATION_IN_PROGRESS)
                logger.debug('TNC registration has been finalized')
                context.middleware.create_task(
                    context.call2(context.s.tn_connect.acme.initiate_cert_generation),
                )
                # Remove claim token from cache
                await context.middleware.call('cache.pop', CLAIM_TOKEN_CACHE_KEY)
                return
        else:
            logger.debug('TNC registration has not been finalized yet: %r', poll_status['error'])

        sleep_secs = calculate_sleep(start_time, BACKOFF_BASE_SLEEP)
        logger.debug('Waiting for %r seconds before attempting to finalize registration', sleep_secs)
        if sleep_secs is not None:
            await asyncio.sleep(sleep_secs)
        config = await context.call2(context.s.tn_connect.config)


async def _poll_once(
    claim_token: str, system_id: str, tnc_config: dict[str, Any],
) -> dict[str, Any]:
    return await tnc_request(
        get_registration_finalization_uri(tnc_config), 'post',
        payload={'system_id': system_id, 'claim_token': claim_token},
    )
