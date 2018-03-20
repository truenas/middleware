import os

from middlewared.alert.base import Alert, AlertLevel, AlertSource


class ServiceMonitorAlertSource(AlertSource):
    level = AlertLevel.WARNING
    title = "Service is not running"

    async def check(self):
        alerts = []
        for file in os.listdir("/tmp/"):
            if file.endswith(".service_monitor"):
                full_path = "/tmp/" + file
                with open(full_path, "r") as _file:
                    for alert_line in _file:
                        alerts.append(Alert(alert_line))

        return alerts
