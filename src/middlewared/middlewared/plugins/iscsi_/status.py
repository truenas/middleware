from middlewared.service import accepts, Service


class ISCSIGlobalService(Service):

    class Config:
        namespace = 'iscsi.global'
        cli_namespace = 'sharing.iscsi.global'

    @accepts(roles=['SHARING_ISCSI_GLOBAL_READ'])
    async def client_count(self):
        """
        Return currently connected clients count.
        """
        return len({host.ip for host in await self.middleware.call("iscsi.host.injection.collect")})
