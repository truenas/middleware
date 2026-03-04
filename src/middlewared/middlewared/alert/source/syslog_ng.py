import subprocess

from middlewared.alert.base import AlertClass, AlertClassConfig, AlertCategory, AlertLevel, Alert, NonDataclassAlertClass, ThreadedAlertSource


class SyslogNgAlert(NonDataclassAlertClass[str], AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.REPORTING,
        level=AlertLevel.WARNING,
        title="syslog-ng Is Not Running",
        text="%s",
    )


class SyslogNgAlertSource(ThreadedAlertSource):
    def check_sync(self):
        p1 = subprocess.Popen(["/usr/sbin/service", "syslog-ng", "status"], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, encoding="utf8")
        status = p1.communicate()[0]
        if p1.returncode == 1:
            return Alert(SyslogNgAlert(status))
