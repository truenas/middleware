# import errno
import os

from .base import SimpleService
# from middlewared.service_exception import CallError
poison_exports_marker = "/var/local/bad_exports_block_nfsd"


class NFSService(SimpleService):
    name = "nfs"
    reloadable = True

    etc = ["nfsd"]

    systemd_unit = "nfs-server"

    async def check_configuration(self):
        # NAS-123498: Eliminate requirement to have shares configured to start NFS
        # But, raise an alarm if there are entries in /etc/exports.d
        exportsd = '/etc/exports.d'
        if os.path.exists(exportsd) and not os.path.isfile(exportsd):
            exportsdList = os.listdir(exportsd)
            if len(exportsdList) > 0:
                await self.middleware.call('alert.oneshot_create', 'NFSblockedByExportsDir', {
                    'entries': exportsdList
                })
            else:
                await self.middleware.call('alert.oneshot_delete', 'NFSblockedByExportsDir', None)

    async def after_start(self):
        await self._systemd_unit("rpc-statd", "start")

    async def stop(self):
        await self._systemd_unit(self.systemd_unit, "stop")
        await self._systemd_unit("rpc-statd", "stop")
        await self._systemd_unit("rpcbind", "stop")
        await self._systemd_unit("rpc-gssd", "stop")
