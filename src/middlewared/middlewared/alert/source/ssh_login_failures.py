import bz2
from datetime import datetime, timedelta
import glob
import gzip
import os
import re

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import CrontabSchedule


def catmsgs():
    log_directory = "/var/log"

    for log_file in sorted(
        filter(
            lambda path: re.match(r".*\.[0-9]+\.[^.]+$", path),
            glob.glob("/var/log/auth.log.*.*"),
        ),
        key=lambda path: int(path.split(".")[-2]),
        reverse=True,
    ):
        if log_file.endswith(".bz2"):
            try:
                with bz2.BZ2File(log_file, "rb") as f:
                    yield from f
            except IOError:
                pass

        if log_file.endswith(".gz"):
            try:
                with gzip.GzipFile(log_file, "rb") as f:
                    yield from f
            except IOError:
                pass

    try:
        with open(os.path.join(log_directory, "auth.log"), "rb") as f:
            yield from f
    except IOError:
        pass


def get_login_failures(now, messages):
    yesterday = (now - timedelta(days=1)).strftime("%b %e ")
    today = now.strftime("%b %e ")

    login_failures = []
    for message in messages:
        message = message.decode("utf-8", "ignore")
        if message.strip():
            if message.startswith(yesterday):
                if re.search(r"\b(fail(ures?|ed)?|invalid|bad|illegal|auth.*error)\b", message, re.I):
                    login_failures.append(message)

            if not message.startswith(yesterday) and not message.startswith(today):
                login_failures = []

    return login_failures


class SSHLoginFailuresAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "SSH Login Failures"
    text = "%(count)d SSH login failures:\n%(failures)s"


class SSHLoginFailuresAlertSource(ThreadedAlertSource):
    schedule = CrontabSchedule(hour=0)

    def check_sync(self):
        login_failures = get_login_failures(datetime.now(), catmsgs())
        if login_failures:
            return Alert(SSHLoginFailuresAlertClass, {
                "count": len(login_failures),
                "failures": "".join(
                    login_failures if len(login_failures) <= 5
                    else login_failures[:2] + [f"... {len(login_failures) - 4} more ...\n"] + login_failures[-2:]
                )
            })
