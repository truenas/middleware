import os

from .base import SimpleService


class NFSService(SimpleService):
    name = "nfs"
    reloadable = True
    systemd_unit_timeout = 10
    may_run_on_standby = False

    etc = ["nfsd"]

    systemd_unit = "nfs-server"

    def check_exportsd_dir(self):
        exports = list()
        try:
            with os.scandir('/etc/exports.d') as scan:
                for i in filter(lambda x: x.is_file() and not x.name.startswith('.'), scan):
                    exports.append(i.name)
        except (FileNotFoundError, NotADirectoryError):
            pass
        return exports

    async def check_configuration(self):
        # Raise alert if there are entries in /etc/exports.d
        if (exportsdList := await self.middleware.run_in_thread(self.check_exportsd_dir)):
            await self.middleware.call('alert.oneshot_create', 'NFSblockedByExportsDir', {'entries': exportsdList})
        else:
            await self.middleware.call('alert.oneshot_delete', 'NFSblockedByExportsDir')

    async def after_start(self):
        await self._systemd_unit("rpc-statd", "start")

    async def stop(self):
        await self._systemd_unit(self.systemd_unit, "stop")
        await self._systemd_unit("rpc-statd", "stop")
        await self._systemd_unit("rpcbind", "stop")
        await self._systemd_unit("rpc-gssd", "stop")
