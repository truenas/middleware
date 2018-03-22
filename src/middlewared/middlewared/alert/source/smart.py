from datetime import timedelta

from freenasUI.services.utils import SmartAlert

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule


class SMARTAlertSource(ThreadedAlertSource):
    level = AlertLevel.CRITICAL
    title = "SMART error"

    hardware = True

    schedule = IntervalSchedule(timedelta(minutes=5))

    def check_sync(self):
        alerts = []

        with SmartAlert() as sa:
            for msgs in sa.data.values():
                if not msgs:
                    continue
                for msg in msgs:
                    if msg is None:
                        continue
                    alerts.append(Alert(msg))

        return alerts
