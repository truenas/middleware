from django.db.models import Q
from django.utils.translation import ugettext as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.storage.models import Replication


class ReplicationStatusAlert(BaseAlert):

    def run(self):
        qs = Replication.objects.filter(repl_enabled=True)
        alerts = []
        for repl in qs:
            if repl.repl_lastresult in ('Succeeded', ''):
                continue
            alerts.append(Alert(
                Alert.CRIT,
                _('Replication %s failed: %s') % (repl, repl.repl_lastresult),
            ))
        return alerts

alertPlugins.register(ReplicationStatusAlert)
