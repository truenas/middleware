import os
from django.utils.translation import ugettext as _

from freenasUI.middleware.notifier import GELI_REKEY_FAILED
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class VolRekeyAlert(BaseAlert):

    def run(self):
        alerts = []
        if os.path.exists(GELI_REKEY_FAILED):
            alerts.append(Alert(Alert.CRIT, _(
                'Encrypted volume failed to rekey some disks. Please make '
                'sure you have working recovery keys, check logs files and '
                'correct the error as it may result to data loss.'
            ), hardware=True))
        return alerts

alertPlugins.register(VolRekeyAlert)
