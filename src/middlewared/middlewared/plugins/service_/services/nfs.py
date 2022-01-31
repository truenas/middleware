from .base import SimpleService


class NFSService(SimpleService):
    name = "nfs"
    reloadable = True

    etc = ["nfsd"]

    systemd_unit = "nfs-server"

    async def stop(self):
        await self._systemd_unit(self.systemd_unit, "stop")
        await self._systemd_unit("rpcbind", "stop")
        await self._systemd_unit("rpc-gssd", "stop")
