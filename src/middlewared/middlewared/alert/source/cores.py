from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, AlertSource, Alert, IntervalSchedule


class CoreFilesArePresentAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Core Files Found in System Database"
    text = ("Core files for the following executables were found: %(corefiles)s. Please create a ticket at "
            "https://jira.ixsystems.com/ and attach the relevant core files along with a system debug. "
            "Once the core files have been archived and attached to the ticket, they may be removed "
            "by running the following command in shell: 'rm /var/db/system/cores/*'.")

    products = ("CORE", "SCALE")


class CoreFilesArePresentAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))

    products = ("SCALE",)

    async def check(self):
        corefiles = []
        for coredump in await self.middleware.call("system.coredumps"):
            if coredump["corefile"] == "present":
                if coredump["exe"] == "/usr/sbin/syslog-ng":
                    continue

                corefiles.append(f"{coredump['exe']} ({coredump['time']})")

        if corefiles:
            return Alert(CoreFilesArePresentAlertClass, {"corefiles": ', '.join(corefiles)})
