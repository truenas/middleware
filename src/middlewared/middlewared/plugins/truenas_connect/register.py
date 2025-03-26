import asyncio
import logging
import uuid
from urllib.parse import urlencode

from truenas_connect_utils.status import Status
from truenas_connect_utils.urls import get_registration_uri

from middlewared.api import api_method
from middlewared.api.current import (
    TNCGetRegistrationURIArgs, TNCGetRegistrationURIResult, TNCGenerateClaimTokenArgs, TNCGenerateClaimTokenResult,
)
from middlewared.service import CallError, Service

from .utils import CLAIM_TOKEN_CACHE_KEY


logger = logging.getLogger('truenas_connect')


class TrueNASConnectService(Service):

    class Config:
        namespace = 'tn_connect'
        cli_private = True

    @api_method(TNCGenerateClaimTokenArgs, TNCGenerateClaimTokenResult, roles=['TRUENAS_CONNECT_WRITE'])
    async def generate_claim_token(self):
        """
        Generate a claim token for TrueNAS Connect.

        This is used to claim the system with TrueNAS Connect. When this endpoint will be called, a token will
        be generated which will be used to assist with initial setup with truenas connect.
        """
        config = await self.middleware.call('tn_connect.config')
        if config['enabled'] is False:
            raise CallError('TrueNAS Connect is not enabled')

        if config['status'] != Status.CLAIM_TOKEN_MISSING.name:
            raise CallError(
                'Claim token has already been generated, either finalize registration '
                'or re-enable TNC to reset claim token'
            )

        claim_token = str(uuid.uuid4())
        # Claim token is going to be valid for 45 minutes
        await self.middleware.call('cache.put', CLAIM_TOKEN_CACHE_KEY, claim_token, 45 * 60)
        await self.middleware.call('tn_connect.set_status', Status.REGISTRATION_FINALIZATION_WAITING.name)
        logger.debug(
            'Claim token for TNC generation has been generated, kicking off registration '
            'process to finalize registration after 1 minute'
        )
        # Triggering the job now to finalize registration
        asyncio.get_event_loop().call_later(
            1 * 60,
            lambda: self.middleware.create_task(
                self.middleware.call('tn_connect.finalize.registration')
            ),
        )
        await self.middleware.call('tn_connect.finalize.registration')
        return claim_token


    @api_method(TNCGetRegistrationURIArgs, TNCGetRegistrationURIResult, roles=['TRUENAS_CONNECT_READ'])
    async def get_registration_uri(self):
        """
        Return the registration URI for TrueNAS Connect.

        Before this endpoint is called, tn_connect must be enabled and a claim token must be generated - based
        off which this endpoint will return the registration URI for TrueNAS Connect.
        """
        config = await self.middleware.call('tn_connect.config')
        if not config['enabled']:
            raise CallError('TrueNAS Connect is not enabled')

        try:
            claim_token = await self.middleware.call('cache.get', CLAIM_TOKEN_CACHE_KEY)
        except KeyError:
            raise CallError(
                'Claim token is not generated. Please generate a claim token before trying to get registration URI'
            ) from None

        query_params = {
            'version': await self.middleware.call('system.version_short'),
            'model': (await self.middleware.call('truenas.get_chassis_hardware')).removeprefix('TRUENAS-'),
            'system_id': await self.middleware.call('system.global.id'),
            'token': claim_token,
        }

        return f'{get_registration_uri(config)}?{urlencode(query_params)}'
