import os

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource


class CoreFilesArePresentAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Core Files Are Present"
    text = ("Core files are present in /var/db/system/cores: %s. Please, file a ticket at https://jira.ixsystems.com/ "
            "and then remove them.")


class CoreFilesArePresentAlertSource(ThreadedAlertSource):
    def check_sync(self):
        try:
            files = sorted(os.listdir("/var/db/system/cores"))
        except Exception:
            files = []

        if files:
            return Alert(CoreFilesArePresentAlertClass, ", ".join(files))
