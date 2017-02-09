from django.utils.translation import ugettext as _
from freenasUI.freeadmin.hook import HookMetaclass
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.middleware.notifier import notifier


class BootVolumeStatusAlert(BaseAlert, metaclass=HookMetaclass):

    __hook_reverse_order__ = False
    name = 'BootVolumeStatus'

    def on_volume_status_not_healthy(self, state, status):
        return Alert(
            Alert.CRIT,
            _('The boot volume state is %(state)s: %(status)s') % {
                'state': state,
                'status': status,
            },
            hardware=True,
        )

    def run(self):
        alerts = []
        state, status = notifier().zpool_status('freenas-boot')
        if state == 'HEALTHY':
            pass
        else:
            alerts.append(
                self.on_volume_status_not_healthy(state, status)
            )
        return alerts

alertPlugins.register(BootVolumeStatusAlert)
