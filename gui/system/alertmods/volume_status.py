from django.utils.translation import ugettext as _
from freenasUI.freeadmin.hook import HookMetaclass
from freenasUI.storage.models import Volume
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.middleware.notifier import notifier


class VolumeStatusAlert(BaseAlert, metaclass=HookMetaclass):

    __hook_reverse_order__ = False
    name = 'VolumeStatus'

    def on_volume_status_not_healthy(self, vol, state, status):
        return Alert(Alert.CRIT, _(
            'The volume %(volume)s state is %(state)s: %(status)s'
        ) % {
            'volume': vol,
            'state': state,
            'status': status,
        }, hardware=True)

    def volumes_status_enabled(self):
        return True

    def run(self):
        if not self.volumes_status_enabled():
            return
        alerts = []
        for vol in Volume.objects.filter(vol_fstype='ZFS'):
            if not vol.is_decrypted():
                continue
            state, status = notifier().zpool_status(vol.vol_name)
            if state == 'HEALTHY':
                pass
            else:
                alerts.append(
                    self.on_volume_status_not_healthy(vol, state, status)
                )
        return alerts

alertPlugins.register(VolumeStatusAlert)
