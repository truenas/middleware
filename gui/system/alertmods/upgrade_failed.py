import os

from django.utils.translation import ugettext as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class UpdateFailedAlert(BaseAlert):

    interval = 60

    def run(self):
        alerts = []
        if os.path.exists('/data/update.failed'):
            alerts.append(
                Alert(
                    Alert.CRIT,
                    _(
                        'Update failed. Check /data/update.failed for further '
                        'details.'
                    ),
                )
            )
        return alerts

alertPlugins.register(UpdateFailedAlert)
