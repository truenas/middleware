import os

from .base import SimpleService

GSSPROXY_PROC = '/proc/net/rpc/use-gss-proxy'
GSSPROXY_ENABLED = 1


class NFSService(SimpleService):
    name = "nfs"
    reloadable = True
    systemd_unit_timeout = 10

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

    def _get_gssproxy_state(self) -> int | None:
        """The kernel must be configured to use gssproxy if kerberos
           is employed with an NFS share."""
        rv = None
        try:
            with open(GSSPROXY_PROC, 'r') as pf:
                val = pf.read().strip()
                rv = int(val)
        except Exception:
            # Treat both missing file (valid possibility) and
            # read or other failure (not really expected) the same
            # by returning None
            pass
        return rv

    async def check_gssproxy_state(self) -> int | None:
        """async wrapper around gssproxy state get
           -1 = unset
            0 = disabled
            1 = enabled
            None = failure to read"""
        return await self.middleware.run_in_thread(self._get_gssproxy_state)

    async def check_configuration(self):
        # Raise alert if there are entries in /etc/exports.d
        if (exportsdList := await self.middleware.run_in_thread(self.check_exportsd_dir)):
            await self.middleware.call('alert.oneshot_create', 'NFSblockedByExportsDir', {'entries': exportsdList})
        else:
            await self.middleware.call('alert.oneshot_delete', 'NFSblockedByExportsDir')

    async def before_start(self):
        # If available, make sure the procfs nfsv4recoverydir entry has the correct info.
        # Usually the update should be done _before_ nfsd is running.
        # Sometimes, after a reboot, the proc entry may not exist and that's ok.
        await self.middleware.call('nfs.update_procfs_v4recoverydir')

    async def after_start(self):
        # This is to cover the case where the proc entry did not exist
        await self.middleware.call('nfs.update_procfs_v4recoverydir')
        await self._systemd_unit("rpc-statd", "start")

        # Confirm use-gss-proxy is enabled
        if await self.check_gssproxy_state() != GSSPROXY_ENABLED:
            # We can most often establish use-gss-proxy=1 with the following:
            await self._systemd_unit("nfs-server", "stop")
            await self._systemd_unit("gssproxy", "restart")
            await self._systemd_unit("nfs-server", "start")

            # Re-check and log if not enabled.  Continue anyway as
            # kerberos is often not required.
            if (use_gss_proxy := self.check_gssproxy_state()) != GSSPROXY_ENABLED:
                self.middleware.logger.warning(
                    f"Failed to enable use-gss-proxy for NFS.  use-gss-proxy is {use_gss_proxy}"
                )

    async def stop(self):
        await self._systemd_unit(self.systemd_unit, "stop")
        await self._systemd_unit("rpc-statd", "stop")
        await self._systemd_unit("rpcbind", "stop")
        await self._systemd_unit("rpc-gssd", "stop")
