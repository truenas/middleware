from .base import SimpleService


class NFSService(SimpleService):
    name = "nfs"
    reloadable = True

    etc = ["nfsd"]

    freebsd_rc = "nfsd"

    systemd_unit = "nfs-ganesha"

    async def _start_freebsd(self):
        await self._freebsd_service("rpcbind", "start")
        await self.middleware.call("nfs.setup_v4")
        await self._freebsd_service("mountd", "start")
        await self._freebsd_service("nfsd", "start")
        await self._freebsd_service("statd", "start")
        await self._freebsd_service("lockd", "start")

    async def _stop_freebsd(self):
        await self._freebsd_service("lockd", "stop", force=True)
        await self._freebsd_service("statd", "stop", force=True)
        await self._freebsd_service("nfsd", "stop", force=True)
        await self._freebsd_service("mountd", "stop", force=True)
        await self._freebsd_service("nfsuserd", "stop", force=True)
        await self._freebsd_service("gssd", "stop", force=True)
        await self._freebsd_service("rpcbind", "stop", force=True)

    async def _reload_freebsd(self):
        await self.middleware.call("nfs.setup_v4")
        await self._freebsd_service("mountd", "reload", force=True)

    async def _stop_linux(self):
        await self._systemd_unit("nfs-ganesha-lock", "stop")
        await super()._stop_linux()
