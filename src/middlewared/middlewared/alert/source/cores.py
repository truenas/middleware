import re

from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, AlertSource, Alert, IntervalSchedule
from middlewared.utils import run


SKIP_REGEX = re.compile(r'Unit:\s+containerd.service')


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
    dumps = {}
    dump_error_logged = []
    schedule = IntervalSchedule(timedelta(hours=6))

    products = ("SCALE",)

    async def check(self):
        corefiles = []
        for coredump in filter(lambda c: c["corefile"] == "present", await self.middleware.call("system.coredumps")):
            if coredump["exe"] == "/usr/sbin/syslog-ng" or coredump["pid"] in self.dump_error_logged:
                continue

            if coredump["pid"] not in self.dumps:
                cp = await run(
                    "coredumpctl", "info", str(coredump["pid"]), check=False, encoding="utf-8", errors="ignore"
                )
                if cp.returncode:
                    self.middleware.logger.debug(
                        "Unable to retrieve coredump information of %r process", coredump["pid"]
                    )
                    self.dump_error_logged.append(coredump["pid"])
                    continue

                self.dumps[coredump["pid"]] = {
                    **coredump,
                    "happened_in_container": bool(SKIP_REGEX.findall(cp.stdout))
                }

            if self.dumps[coredump["pid"]]["happened_in_container"]:
                # We don't want to raise an alert to user about a container which died for some reason
                continue

            corefiles.append(f"{coredump['exe']} ({coredump['time']})")

        if corefiles:
            return Alert(CoreFilesArePresentAlertClass, {"corefiles": ', '.join(corefiles)})
