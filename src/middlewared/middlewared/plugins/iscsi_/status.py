from middlewared.api import api_method
from middlewared.api.current import ISCSIGlobalClientCountArgs, ISCSIGlobalClientCountResult
from middlewared.service import Service


class ISCSIGlobalService(Service):

    class Config:
        namespace = 'iscsi.global'
        cli_namespace = 'sharing.iscsi.global'

    @api_method(
        ISCSIGlobalClientCountArgs,
        ISCSIGlobalClientCountResult,
        roles=['SHARING_ISCSI_GLOBAL_READ']
    )
    async def client_count(self):
        """
        Return currently connected clients count.
        """
        addrs = await self.middleware.call('iscsi.global.sessions', [], {'select': ['initiator_addr']})
        return len({addr['initiator_addr'] for addr in addrs})
