from middlewared.service import CallError, Service
from middlewared.utils.version import parse_version_string

from .mixin import TNCAPIMixin
from .status_utils import Status
from .utils import get_account_id_and_system_id
from .urls import get_heartbeat_url


class TNCHeartbeatService(Service, TNCAPIMixin):

    class Config:
        namespace = 'tn_connect.heartbeat'
        private = True

    async def call(self, url, mode, payload=None):
        config = await self.middleware.call('tn_connect.config_internal')
        return await self._call(url, mode, payload=payload, headers=await self.auth_headers(config))

    async def start(self):
        tnc_config = await self.middleware.call('tn_connect.config_internal')
        if tnc_config['status'] != Status.CONFIGURED.name:
            raise CallError('TrueNAS Connect is not configured properly')

        heartbeat_url = get_heartbeat_url(tnc_config).format(
            system_id=get_account_id_and_system_id(tnc_config)['system_id'],
            version=parse_version_string(await self.middleware.call('system.version_short')),
        )

    async def payload(self):
        pass
