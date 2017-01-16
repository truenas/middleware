import os
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class ServiceMonitor(BaseAlert):

    def run(self):

        alerts = []

        for file in os.listdir("/tmp/"):
            if file.endswith(".service_monitor"):
                full_path = '/tmp/' + file
                with open(full_path, 'r') as _file:
                    for alert_line in _file:
                        alerts.append(Alert(Alert.WARN, alert_line))

        return alerts

alertPlugins.register(ServiceMonitor)
