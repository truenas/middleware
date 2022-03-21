from .base import SimpleService


class NFSService(SimpleService):
    name = "nfs"
    reloadable = True

    etc = ["nfsd"]

    systemd_unit = "nfs-server"

    async def systemd_extra_units(self):
        return ["rpc-statd"]

    async def after_start(self):
        await self._systemd_unit("rpc-statd", "start")

    async def stop(self):
        await self._systemd_unit(self.systemd_unit, "stop")
        await self._systemd_unit("rpc-statd", "stop")
        await self._systemd_unit("rpcbind", "stop")
        await self._systemd_unit("rpc-gssd", "stop")
