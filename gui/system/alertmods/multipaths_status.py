from django.utils.translation import ugettext as _

from freenasUI.middleware.notifier import notifier
from freenasUI.middleware.connector import connection as dispatcher
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from fnutils.query import wrap


class MultipathAlert(BaseAlert):

    def run(self):
        not_optimal = []
        for disk in wrap(dispatcher.call_sync('disks.query')):
            if not disk.get('is_multipath'):
                continue

            if disk['multipath.status'] != 'OPTIMAL':
                not_optimal.append(disk['path'])

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
