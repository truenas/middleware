import os
import json
import middlewared.logger

from django.utils.translation import ugettext as _
from freenasOS.Update import PendingUpdates
from freenasUI.middleware.notifier import notifier
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.system.models import Update
from freenasUI.system.utils import is_update_applied

UPDATE_APPLIED_SENTINEL = '/tmp/.updateapplied'

log = middlewared.logger.Logger('update_check_alertmod')


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


class UpdateAppliedAlert(BaseAlert):

    interval = 10

    def run(self):
        alerts = []

        if os.path.exists(UPDATE_APPLIED_SENTINEL):
            try:
                with open(UPDATE_APPLIED_SENTINEL, 'rb') as f:
                    data = json.loads(f.read().decode('utf8'))
            except:
                log.error(
                    'Could not load UPDATE APPLIED SENTINEL located at {0}'.format(
                        UPDATE_APPLIED_SENTINEL
                    ),
                    exc_info=True
                )
                return alerts
            update_applied, msg = is_update_applied(data['update_version'], create_alert=False)
            if update_applied:
                alerts.append(Alert(Alert.WARN, _(msg)))
        return alerts

alertPlugins.register(UpdateCheckAlert)
alertPlugins.register(UpdateAppliedAlert)
