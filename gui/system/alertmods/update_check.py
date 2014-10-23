from django.utils.translation import ugettext as _

from freenasOS.Update import CheckForUpdates
from freenasUI.middleware.notifier import notifier
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.system.models import Update


class UpdateCheckAlert(BaseAlert):

    def run(self):
        alerts = []
        try:
            update = Update.objects.order_by('-id')[0]
        except IndexError:
            update = Update.objects.create()

        path = notifier().system_dataset_path()
        if not path:
            return None
        try:
            check = CheckForUpdates(train=update.get_train(), cache_dir=path)
        except:
            check = None
        if check:
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
