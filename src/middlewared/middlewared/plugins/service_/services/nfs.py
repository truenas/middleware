import os
import subprocess

from middlewared.alert.source.nfs_exportsd import NFSblockedByExportsDirAlert

from .base import SimpleService


class NFSService(SimpleService):
    name = "nfs"
    reloadable = True
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
        # nfs-idmapd requires rpc_pipefs to be mounted. rpc_pipefs is normally
        # mounted at boot by a systemd generator that reads pipefs-directory
        # from /etc/nfs.conf. On first boot, nfs.conf does not exist yet when
        # generators run, so rpc_pipefs.target is never created and nfs-idmapd
        # will fail to start. By this point generate_etc has written nfs.conf.
        # A daemon-reload re-runs the generator, which creates the target and
        # mounts rpc_pipefs so that nfs-idmapd can start with nfs-server.
        if not os.path.ismount('/run/rpc_pipefs'):
            await self.middleware.run_in_thread(
                subprocess.run, ['systemctl', 'daemon-reload'], capture_output=True
            )

        # Raise alert if there are entries in /etc/exports.d
        if (exportsdList := await self.middleware.run_in_thread(self.check_exportsd_dir)):
            await self.middleware.call('alert.oneshot_create', NFSblockedByExportsDirAlert(entries=str(exportsdList)))
        else:
            await self.middleware.call('alert.oneshot_delete', 'NFSblockedByExportsDir')

    async def after_start(self):
        await self._systemd_unit("rpc-statd", "start")

    async def stop(self):
        await self._systemd_unit(self.systemd_unit, "stop")
        await self._systemd_unit("rpc-statd", "stop")
        await self._systemd_unit("rpcbind", "stop")
        await self._systemd_unit("rpc-gssd", "stop")
