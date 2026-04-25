from __future__ import annotations

import logging

from truenas_connect_utils.status import Status

from middlewared.service import ServiceContext

from .finalize_registration import status_update
from .utils import CONFIGURED_TNC_STATES


logger = logging.getLogger('truenas_connect')


async def state_check_impl(context: ServiceContext, restart_ui: bool = False) -> None:
    tnc_config = await context.call2(context.s.tn_connect.config)
    if tnc_config.status == Status.REGISTRATION_FINALIZATION_WAITING.name:
        logger.debug(
            'Registration finalization failed as middleware was restarted while waiting '
            'for TNC registration finalization'
        )
        # This means middleware got restarted or the system was rebooted while we were waiting for
        # registration to finalize, so in this case we set the state to registration failed
        await status_update(context, Status.REGISTRATION_FINALIZATION_FAILED)
    elif tnc_config.status == Status.CERT_GENERATION_IN_PROGRESS.name:
        logger.debug('Middleware started and cert generation is in progress, initiating process')
        context.middleware.create_task(context.call2(context.s.tn_connect.acme.initiate_cert_generation))
    elif tnc_config.status in (
        Status.CERT_GENERATION_SUCCESS.name, Status.CERT_RENEWAL_SUCCESS.name,
    ):
        logger.debug('Middleware started and cert generation is already successful, updating UI')
        context.middleware.create_task(context.call2(context.s.tn_connect.acme.update_ui))
    elif tnc_config.status == Status.CERT_RENEWAL_IN_PROGRESS.name:
        logger.debug('Middleware started and cert renewal is in progress, initiating process')
        context.middleware.create_task(context.call2(context.s.tn_connect.acme.renew_cert))

    if tnc_config.status in CONFIGURED_TNC_STATES:
        logger.debug('Triggering heartbeat start')
        context.middleware.create_task(context.call2(context.s.tn_connect.heartbeat_start))
        if restart_ui:
            logger.debug('Restarting UI')
            await context.middleware.call('system.general.ui_restart', 2)
