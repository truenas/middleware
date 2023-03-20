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
    ignore_executables = (
        # Crashes at https://github.com/smartmontools/smartmontools/blob/6cc32bf/smartmontools/knowndrives.cpp#L98
        # when trying to run `-d sat` against certain drives. This is clearly a memory corruption issue since
        # allocation/freeing in that class is pretty straightforward. Things like that are very hard to debug.
        # If it crashes with `-d sat` (which is a first try) we simply run it normally so these segfaults are not
        # a big deal.
        "/usr/sbin/smartctl",
    )
    ignore_units = (
        # Unit: "syslog-ng.service" has been core dumping for, literally, years
        # on freeBSD and now also on linux. The fix is non-trivial and it seems
        # to be very specific to how we implemented our system dataset. Anyways,
        # the crash isn't harmful so we ignore it.
        "syslog-ng.service",
        # Users are free to run whatever 3rd party software in their "app" that they
        # so choose. We can't fix all the problems of k3s so ignore them since they're
        # harmless and only cause unnecessary tickets to be created.
        "k3s.service",
    )

    async def check(self):
        corefiles = []
        for coredump in filter(lambda c: c["corefile"] == "present", await self.middleware.call("system.coredumps")):
            if coredump["exe"] in self.ignore_executables or coredump["unit"] in self.ignore_units:
                continue

            corefiles.append(f"{coredump['exe']} ({coredump['time']})")

        if corefiles:
            return Alert(CoreFilesArePresentAlertClass, {"corefiles": ', '.join(corefiles)})
