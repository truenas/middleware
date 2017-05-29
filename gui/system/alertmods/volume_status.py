from django.utils.translation import ugettext as _
from freenasUI.freeadmin.hook import HookMetaclass
from freenasUI.storage.models import Volume
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.middleware.notifier import notifier


class VolumeStatusAlert(BaseAlert):

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
        if not notifier().is_freenas():
            status = notifier().failover_status()
            return status in ('MASTER', 'SINGLE')
        return True

    def run(self):
        if not self.volumes_status_enabled():
            return
        alerts = []
        for vol in Volume.objects.all():
            if not vol.is_decrypted():
                continue
            state, status = notifier().zpool_status(vol.vol_name)
            if state != 'HEALTHY':
                if not notifier().is_freenas():
                    try:
                        notifier().zpool_enclosure_sync(vol.vol_name)
                    except:
                        pass
                alerts.append(
                    self.on_volume_status_not_healthy(vol, state, status)
                )
        return alerts

alertPlugins.register(VolumeStatusAlert)
