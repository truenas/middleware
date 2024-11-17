import uuid
from urllib.parse import urlencode

from middlewared.api import api_method
from middlewared.api.current import (
    TNCGetRegistrationURIArgs, TNCGetRegistrationURIResult, TNCGenerateClaimTokenArgs, TNCGenerateClaimTokenResult,
)
from middlewared.service import CallError, Service

from .urls import REGISTRATION_URI


class TrueNASConnectService(Service):

    class Config:
        namespace = 'tn_connect'
        cli_private = True

    @api_method(TNCGenerateClaimTokenArgs, TNCGenerateClaimTokenResult)
    async def generate_claim_token(self):
        """
        Generate a claim token for TrueNAS Connect.

        This is used to claim the system with TrueNAS Connect. When this endpoint will be called, a token will
        be generated which will be used to assist with initial setup with truenas connect.
        """
        # FIXME: Handle the case where TNC is already configured and this is called
        config = await self.middleware.call('tn_connect.config')
        config['claim_token'] = str(uuid.uuid4())
        await self.middleware.call(
            'datastore.update', 'truenas_connect', config['id'], {'claim_token': config['claim_token']}
        )
        return config['claim_token']


    @api_method(TNCGetRegistrationURIArgs, TNCGetRegistrationURIResult)
    async def get_registration_uri(self):
        """
        Return the registration URI for TrueNAS Connect.

        Before this endpoint is called, tn_connect must be enabled and a claim token must be generated - based
        off which this endpoint will return the registration URI for TrueNAS Connect.
        """
        config = await self.middleware.call('tn_connect.config')
        if not config['enabled']:
            raise CallError('TrueNAS Connect is not enabled')
        if not config['claim_token']:
            raise CallError('Claim token must be explicitly generated before registration URI is requested')

        query_params = {
            'version': await self.middleware.call('system.version_short'),
            'model': (await self.middleware.call('truenas.get_chassis_hardware')).removeprefix('TRUENAS-'),
            'system_id': await self.middleware.call('system.host_id'),
            'token': config['claim_token'],
        }

        return f'{REGISTRATION_URI}?{urlencode(query_params)}'
