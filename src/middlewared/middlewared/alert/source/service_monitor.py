import os

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class ServiceMonitorAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "Domain Controller Service Is Not Running"
    text = "%s."


class ServiceMonitorAlertSource(AlertSource):
    async def check(self):
        alerts = []
        for file in os.listdir("/tmp/"):
            if file.endswith(".service_monitor"):
                full_path = "/tmp/" + file
                with open(full_path, "r") as _file:
                    for alert_line in _file:
                        alerts.append(Alert(ServiceMonitorAlertClass, alert_line))

        return alerts
