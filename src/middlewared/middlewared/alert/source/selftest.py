from datetime import timedelta
import os
import re

from freenasUI.system.ixselftests import ALERT_FILE, TEST_PASS, TEST_WARNING, TEST_FAIL, TEST_CRITICAL

from middlewared.alert.base import Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule


class SelfTestAlertSource(AlertSource):
    level = AlertLevel.WARNING
    title = "Self-test error"

    schedule = IntervalSchedule(timedelta(minutes=5))

    async def check(self):
        alerts = []
        regexp = re.compile(r"\[(.*)\] (.*)")
        if os.path.exists(ALERT_FILE):
            with open(ALERT_FILE) as f:
                for line in f:
                    line = line.rstrip()
                    # Line looks like [PASS|FAIL]<text>, maybe other tags
                    match = regexp.match(line)
                    level = AlertLevel.WARNING
                    if match:
                        if match.group(1) in (TEST_WARNING):
                            level = AlertLevel.WARNING
                        elif match.group(1) in (TEST_FAIL, TEST_CRITICAL):
                            level = AlertLevel.WARNING
                        elif match.group(1) in (TEST_PASS):
                            continue
                        alerts.append(Alert(match.group(2), level=level))
                    else:
                        alerts.append(Alert(line, level=level))

        return alerts
