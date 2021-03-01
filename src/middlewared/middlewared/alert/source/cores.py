import os
import time

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.utils.osc import IS_FREEBSD


class CoreFilesArePresentAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Core Files Found in System Database"
    text = ("The following system core files were found: %(corefiles)s. Please create a ticket at "
            "https://jira.ixsystems.com/ and attach the relevant core files along with a system debug. "
            "Once the core files have been archived and attached to the ticket, they may be removed "
            "by running the following command in shell: 'rm /var/db/system/cores/*'.")

    products = ("CORE", "SCALE")


class CoreFilesArePresentAlertSource(ThreadedAlertSource):
    products = ("CORE", "SCALE")

    def check_sync(self):
        cores = "/var/db/system/cores"
        corefiles = []

        try:
            listdir = os.listdir(cores)
        except Exception:
            return

        for file in listdir:
            if not file.endswith(".core"):
                continue

            path = os.path.join(cores, file)
            if not os.path.isfile(path):
                continue

            unlink = False
            if IS_FREEBSD and file == "syslog-ng.core":
                unlink = True
            elif file == "su.core":
                unlink = True
            elif os.stat(path).st_mtime < time.time() - 86400 * 5:
                unlink = True
            else:
                corefiles.append(file)

            if unlink:
                os.unlink(path)

        if corefiles:
            return Alert(CoreFilesArePresentAlertClass, {"corefiles": ', '.join(corefiles)})
