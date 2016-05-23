import os

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class ADAlert(BaseAlert):

    def run(self):

        alerts = []

        if os.path.exists('/tmp/.adalert'):
            alerts.append(Alert(Alert.WARN, "ActiveDirectory did not bind to the domain"))

        return alerts

alertPlugins.register(ADAlert)
