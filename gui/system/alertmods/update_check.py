from django.utils.translation import ugettext as _

from freenasOS.Update import PendingUpdates
from freenasUI.middleware.notifier import notifier
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.system.models import Update


class UpdateCheckAlert(BaseAlert):

    interval = 60

    def run(self):
        alerts = []
        try:
            Update.objects.order_by('-id')[0]
        except IndexError:
            Update.objects.create()

        path = notifier().get_update_location()
        if not path:
            return None
        try:
            updates = PendingUpdates(path)
        except:
            updates = None

        if updates:
            alerts.append(
                Alert(
                    Alert.OK,
                    _(
                        'There is a new update available! Apply it in System '
                        '-> Update tab.'
                    ),
                )
            )
        return alerts

alertPlugins.register(UpdateCheckAlert)
