import os
import time

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.utils.osc import IS_FREEBSD


class CoreFilesArePresentAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Core Files Found in System Database"
    text = ("System core files were found in /var/db/system/cores. Please create a ticket at "
            "https://jira.ixsystems.com/ and remove these files.")


class CoreFilesArePresentAlertSource(ThreadedAlertSource):
    def check_sync(self):
        cores = "/var/db/system/cores"
        try:
            listdir = os.listdir(cores)
        except Exception:
            return

        has_core_file = False
        for file in listdir:
            if not file.endswith(".core"):
                continue

            path = os.path.join(cores, file)
            if not os.path.isfile(path):
                continue

            unlink = False
            if IS_FREEBSD and file == "syslog-ng.core":
                unlink = True
            elif os.stat(path).st_mtime < time.time() - 86400 * 5:
                unlink = True
            else:
                has_core_file = True

            if unlink:
                os.unlink(path)

        if has_core_file:
            return Alert(CoreFilesArePresentAlertClass)
