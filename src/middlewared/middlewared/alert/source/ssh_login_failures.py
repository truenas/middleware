from collections import deque
from datetime import datetime, timedelta

from systemd import journal

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource


class SSHLoginFailuresAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "SSH Login Failures"
    text = "%(count)d SSH login failures in the last 24 hours:\n%(failures)s"


class SSHLoginFailuresAlertSource(ThreadedAlertSource):
    def check_sync(self):
        j = journal.Reader()
        j.add_match("SYSLOG_IDENTIFIER=sshd")
        j.seek_realtime(datetime.now() - timedelta(days=1))
        count = 0
        last_messages = deque([], 4)
        for record in j:
            if record["MESSAGE"].startswith("Failed password for"):
                count += 1
                last_messages.append(
                    f"{record['__REALTIME_TIMESTAMP'].strftime('%d %b %H:%M:%S')}: {record['MESSAGE']}"
                )

        if count > 0:
            return Alert(SSHLoginFailuresAlertClass, {
                "count": count,
                "failures": "\n".join(
                    ([f"... first {count - len(last_messages)} messages skipped ..."] if count > len(last_messages)
                     else []) +
                    list(last_messages)
                )
            }, key=list(last_messages))
