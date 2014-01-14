from django.utils.translation import ugettext_lazy as _

from freenasUI.middleware.notifier import notifier
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class MultipathAlert(BaseAlert):

    def run(self):
        not_optimal = []
        for mp in notifier().multipath_all():
            if mp.status != 'OPTIMAL':
                not_optimal.append(mp.name)

        if not_optimal:
            return [
                Alert(
                    Alert.CRIT,
                    _('The following multipaths are not optimal: %s') % (
                        ', '.join(not_optimal),
                    )
                )
            ]

alertPlugins.register(MultipathAlert)
