import os

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class LDAPStatusAlert(BaseAlert):

    def run(self):

        alerts = []

        if os.path.exists('/tmp/.ldap_status_alert'):
            alerts.append(Alert(Alert.WARN, "LDAP did not bind to the domain"))

        return alerts

alertPlugins.register(LDAPStatusAlert)
