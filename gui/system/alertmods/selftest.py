import os
import re

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.system.ixselftests import (ALERT_FILE,
                                          TEST_PASS,
                                          TEST_WARNING,
                                          TEST_FAIL,
                                          TEST_CRITICAL)


class ixSelfTestAlert(BaseAlert):

    interval = 5

    def run(self):
        alerts = []
        regexp = re.compile(r"\[(.*)\] (.*)")
        if os.path.exists(ALERT_FILE):
            with open(ALERT_FILE) as f:
                for line in f:
                    line = line.rstrip()
                    # Line looks like [PASS|FAIL]<text>, maybe other tags
                    match = regexp.match(line)
                    lvl = Alert.WARN
                    if match:
                        if match.group(1) in (TEST_WARNING):
                            lvl = Alert.WARN
                        elif match.group(1) in (TEST_FAIL, TEST_CRITICAL):
                            lvl = Alert.CRIT
                        elif match.group(1) in (TEST_PASS):
                            lvl = Alert.OK
                        alerts.append(Alert(lvl, match.group(2)))
                    else:
                        alerts.append(Alert(lvl, line))
        return alerts


alertPlugins.register(ixSelfTestAlert)
