from django.db.models import Q
from django.utils.translation import ugettext as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.storage.models import Replication


class ReplicationStatusAlert(BaseAlert):

    def run(self):
        qs = Replication.objects.filter(repl_enabled=True).exclude(
            Q(repl_lastresult='Succeeded') | Q(repl_lastresult='')
        )
        alerts = []
        for repl in qs:
            alerts.append(Alert(
                Alert.ERROR,
                _('Replication %s failed: %s') % (repl, repl.repl_lastresult),
            ))
        return alerts

alertPlugins.register(ReplicationStatusAlert)
