import errno
import os

from .base import SimpleService
from middlewared.service_exception import CallError


class NFSService(SimpleService):
    name = "nfs"
    reloadable = True

    etc = ["nfsd"]

    systemd_unit = "nfs-server"

    async def check_configuration(self):
        if not await self.middleware.run_in_thread(os.path.exists, '/etc/exports'):
            raise CallError(
                'At least one configured and available NFS export is required '
                'in order to start the NFS service. Check the NFS share configuration '
                'and availability of any paths currently being exported.',
                errno.EINVAL
            )

    async def systemd_extra_units(self):
        return ["rpc-statd"]

    async def after_start(self):
        await self._systemd_unit("rpc-statd", "start")

    async def stop(self):
        await self._systemd_unit(self.systemd_unit, "stop")
        await self._systemd_unit("rpc-statd", "stop")
        await self._systemd_unit("rpcbind", "stop")
        await self._systemd_unit("rpc-gssd", "stop")
