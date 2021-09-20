from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, AlertSource, Alert


class CoreFilesArePresentAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Core Files Found in System Dataset"
    text = ("Core files for the following executables were found: %(corefiles)s. Please create a ticket at "
            "https://jira.ixsystems.com/ and attach the relevant core files along with a system debug. "
            "Once the core files have been archived and attached to the ticket, they may be removed "
            "by running the following command in shell: 'rm /var/db/system/cores/*'.")

    products = ("SCALE",)


class CoreFilesArePresentAlertSource(AlertSource):
    products = ("SCALE",)
    ignore = ("syslog-ng.service", "containerd.service")

    async def check(self):
        corefiles = []
        for coredump in filter(lambda c: c["corefile"] == "present", await self.middleware.call("system.coredumps")):
            if coredump["unit"] in self.ignore:
                # Unit: "syslog-ng.service" has been core dumping for, literally, years
                # on freeBSD and now also on linux. The fix is non-trivial and it seems
                # to be very specific to how we implemented our system dataset. Anyways,
                # the crash isn't harmful so we ignore it.

                # Unit: "containerd.service" is related to k3s.
                # users are free to run whatever they would like to in containers
                # and we don't officially support all the apps themselves so we
                # ignore those core dumps
                continue

            corefiles.append(f"{coredump['exe']} ({coredump['time']})")

        if corefiles:
            return Alert(CoreFilesArePresentAlertClass, {"corefiles": ', '.join(corefiles)})
