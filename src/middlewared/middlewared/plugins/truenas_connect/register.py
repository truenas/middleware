from __future__ import annotations

import asyncio
import errno
import logging
from typing import Any
from urllib.parse import urlencode

from truenas_connect_utils.status import Status
from truenas_connect_utils.urls import get_registration_uri

from middlewared.service import CallError, ServiceContext
from middlewared.utils.crypto import ssl_uuid4

from .internal import config_internal, set_status
from .utils import CLAIM_TOKEN_CACHE_KEY


logger = logging.getLogger('truenas_connect')


async def generate_claim_token_impl(context: ServiceContext) -> str:
    """
    Generate a claim token for TrueNAS Connect.

    This is used to claim the system with TrueNAS Connect. When this endpoint will be called, a token will
    be generated which will be used to assist with initial setup with truenas connect.
    """
    config = await context.call2(context.s.tn_connect.config)
    if config.enabled is False:
        raise CallError('TrueNAS Connect is not enabled')

    if config.status not in (Status.CLAIM_TOKEN_MISSING.name, Status.REGISTRATION_FINALIZATION_TIMEOUT.name):
        raise CallError(
            'Claim token has already been generated, please finalize registration before generating a new one',
            errno=errno.EEXIST,
        )

    claim_token = str(ssl_uuid4())
    # Claim token is going to be valid for 45 minutes
    await context.middleware.call('cache.put', CLAIM_TOKEN_CACHE_KEY, claim_token, 45 * 60)
    await set_status(context, Status.REGISTRATION_FINALIZATION_WAITING.name)
    logger.debug(
        'Claim token for TNC generation has been generated, kicking off registration '
        'process to finalize registration after 30 seconds'
    )
    # Triggering the job now to finalize registration
    # It will start after 30 seconds
    asyncio.get_event_loop().call_later(
        30,
        lambda: context.middleware.create_task(
            context.call2(context.s.tn_connect.finalize.registration)
        ),
    )
    return claim_token


async def get_registration_uri_impl(context: ServiceContext) -> str:
    """
    Return the registration URI for TrueNAS Connect.

    Before this endpoint is called, tn_connect must be enabled and a claim token must be generated - based
    off which this endpoint will return the registration URI for TrueNAS Connect.
    """
    config = await context.call2(context.s.tn_connect.config)
    if not config.enabled:
        raise CallError('TrueNAS Connect is not enabled')

    try:
        claim_token = await context.middleware.call('cache.get', CLAIM_TOKEN_CACHE_KEY)
    except KeyError:
        raise CallError(
            'Claim token is not generated. Please generate a claim token before trying to get registration URI'
        ) from None

    query_params: dict[str, Any] = {
        'version': await context.middleware.call('system.version_short'),
        'model': (await context.middleware.call('truenas.get_chassis_hardware')).removeprefix('TRUENAS-'),
        'system_id': await context.middleware.call('system.global.id'),
        'token': claim_token,
        'port': (await context.middleware.call('system.general.config'))['ui_httpsport']
    }

    # Add license information if valid license exists
    license_info = await context.middleware.call('system.license', True)
    if license_info is not None and not license_info.get('expired', True):
        query_params['license'] = license_info['raw_license']

    # get_registration_uri composes from raw config dict — pass config_internal()'s dict shape.
    raw_config = await config_internal(context)
    return f'{get_registration_uri(raw_config)}?{urlencode(query_params)}'
