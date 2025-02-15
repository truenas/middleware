from middlewared.api import api_method
from middlewared.api.current import IscsiGlobalClientCountArgs, IscsiGlobalClientCountResult
from middlewared.service import Service


class ISCSIGlobalService(Service):

    class Config:
        namespace = 'iscsi.global'
        cli_namespace = 'sharing.iscsi.global'

    @api_method(
        IscsiGlobalClientCountArgs,
        IscsiGlobalClientCountResult,
        roles=['SHARING_ISCSI_GLOBAL_READ']
    )
    async def client_count(self):
        """
        Return currently connected clients count.
        """
        addrs = await self.middleware.call('iscsi.global.sessions', [], {'select': ['initiator_addr']})
        return len({addr['initiator_addr'] for addr in addrs})
