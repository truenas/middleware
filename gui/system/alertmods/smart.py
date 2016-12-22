import logging

from freenasUI.services.utils import SmartAlert
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert

log = logging.getLogger('system.alertmods.smart')


class SMARTAlert(BaseAlert):

    interval = 5

    def run(self):
        alerts = []

        with SmartAlert() as sa:
            for msgs in sa.data.itervalues():
                if not msgs:
                    continue
                for msg in msgs:
                    if msg is None:
                        continue
                    alerts.append(Alert(Alert.CRIT, msg, hardware=True))

        return alerts

alertPlugins.register(SMARTAlert)
