from django.utils.translation import ugettext as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.storage.models import Replication


class ReplicationStatusAlert(BaseAlert):

    def run(self):
        qs = Replication.objects.filter(repl_enabled=True)
        alerts = []
        for repl in qs:
            if repl.repl_lastresult.get('msg') in ('Succeeded', 'Up to date', 'Waiting', 'Running', '', None):
                continue
            alerts.append(Alert(
                Alert.CRIT,
                _('Replication %(replication)s failed: %(message)s') % {
                    'replication': repl,
                    'message': repl.repl_lastresult.get('msg'),
                },
            ))
        return alerts


alertPlugins.register(ReplicationStatusAlert)
