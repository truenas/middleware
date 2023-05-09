from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, AlertSource, Alert


class CoreFilesArePresentAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Core Files Detected"
    text = (
        "Core files for executables have been found in /var/db/system/cores/."
        "Please open the shell, copy any core files present in /var/db/system/cores/ "
        "and then generate a system debug. Next, create a ticket at https://ixsystems.atlassian.net/ "
        "and attach the core files and debug. After creating the ticket, the core files can be removed "
        "from the system by opening shell and entering 'rm /var/db/system/cores/*'."
    )
    products = ("SCALE",)


class CoreFilesArePresentAlertSource(AlertSource):
    products = ("SCALE",)

    async def should_alert(self, core):
        if core["corefile"] != "present" or not core["unit"]:
            # no core file on disk, no investigation
            # not associated to a unit? probably impossible but better safe than sorry
            return False

        return core["unit"].startswith((
            # NFS related service(s)
            "nfs-blkmap.service",
            "nfs-idmapd.service",
            "nfs-mountd.service",
            "nfsdcld.service",
            "rpc-statd.service",
            "rpcbind.service",
            # SMB related service(s)
            "smbd.service",
            "winbind.service",
            "nmbd.service",
            "wsdd.service",
            # SCST related service(s)
            "scst.service",
            # ZFS related (userspace) service(s)
            "zfs-zed.service",
        ))

    async def check(self):
        corefiles = []
        for coredump in await self.middleware.call("system.coredumps"):
            if await self.should_alert(coredump):
                corefiles.append(f"{coredump['exe']} ({coredump['time']})")

        if corefiles:
            return Alert(CoreFilesArePresentAlertClass, {"corefiles": ', '.join(corefiles)})
