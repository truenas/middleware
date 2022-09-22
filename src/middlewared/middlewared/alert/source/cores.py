from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, AlertSource, Alert


class CoreFilesArePresentAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Core Files Found in System Dataset"
    text = ("Core files for the following executables were found: %(corefiles)s. Please create a ticket at "
            "https://ixsystems.atlassian.net/ and attach the relevant core files along with a system debug. "
            "Once the core files have been archived and attached to the ticket, they may be removed "
            "by running the following command in shell: 'rm /var/db/system/cores/*'.")

    products = ("SCALE",)


class CoreFilesArePresentAlertSource(AlertSource):
    products = ("SCALE",)
    ignore_executables = (
        # Crashes at https://github.com/smartmontools/smartmontools/blob/6cc32bf/smartmontools/knowndrives.cpp#L98
        # when trying to run `-d sat` against certain drives. This is clearly a memory corruption issue since
        # allocation/freeing in that class is pretty straightforward. Things like that are very hard to debug.
        # If it crashes with `-d sat` (which is a first try) we simply run it normally so these segfaults are not
        # a big deal.
        "/usr/sbin/smartctl",
    )
    ignore_units = (
        # Unit: "containerd.service"/"docker.service" is related to k3s.
        # users are free to run whatever they would like to in containers
        # and we don't officially support all the apps themselves so we
        # ignore those core dumps
        "containerd.service",
        "docker.service",
        # Unit: "syslog-ng.service" has been core dumping for, literally, years
        # on freeBSD and now also on linux. The fix is non-trivial and it seems
        # to be very specific to how we implemented our system dataset. Anyways,
        # the crash isn't harmful so we ignore it.
        "syslog-ng.service",
    )

    async def check(self):
        corefiles = []
        for coredump in filter(lambda c: c["corefile"] == "present", await self.middleware.call("system.coredumps")):
            if coredump["exe"] in self.ignore_executables:
                continue
            if coredump["unit"] in self.ignore_units:
                continue

            corefiles.append(f"{coredump['exe']} ({coredump['time']})")

        if corefiles:
            return Alert(CoreFilesArePresentAlertClass, {"corefiles": ', '.join(corefiles)})
