import os, subprocess

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.services.models import services

class SMARTDAlert(BaseAlert):

    def run(self):

        alerts = []

        if (services.objects.get(srv_service='smartd').srv_enable):
            p1 = subprocess.Popen(["/usr/sbin/service","smartd","status"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            status = p1.communicate()[0]
            if p1.returncode == 1:
                alerts.append(Alert(Alert.WARN, status))
            else:
                return None
        else:
            return None

        return alerts

alertPlugins.register(SMARTDAlert)
