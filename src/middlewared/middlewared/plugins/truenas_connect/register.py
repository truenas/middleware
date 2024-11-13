import uuid
from urllib.parse import urlencode

from middlewared.api import api_method
from middlewared.api.current import TNCGetRegistrationURIArgs, TNCGetRegistrationURIResult
from middlewared.service import Service

from .urls import REGISTRATION_URI


class TrueNASConnectService(Service):

    class Config:
        namespace = 'tn_connect'
        cli_private = True

    @api_method(TNCGetRegistrationURIArgs, TNCGetRegistrationURIResult)
    async def get_registration_uri(self):
        query_params = {
            'version': await self.middleware.call('system.version_short'),
            'model': (await self.middleware.call('truenas.get_chassis_hardware')).removeprefix('TRUENAS-'),
            'system_id': await self.middleware.call('system.host_id'),
            'token': str(uuid.uuid4()),
        }

        return f'{REGISTRATION_URI}?{urlencode(query_params)}'
