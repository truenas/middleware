import subprocess

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource


class SyslogNgAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "syslog-ng Is Not Running"

    def check_sync(self):
        p1 = subprocess.Popen(["/usr/sbin/service", "syslog-ng", "status"], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, encoding="utf8")
        status = p1.communicate()[0]
        if p1.returncode == 1:
            return Alert(status)
