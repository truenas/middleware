import subprocess

from django.utils.translation import ugettext as _

from freenasUI.middleware.notifier import notifier
from freenasUI.storage.models import Volume
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class VolumeVersionAlert(BaseAlert):

    def run(self):
        alerts = []
        _n = notifier()
        for vol in Volume.objects.filter(vol_fstype='ZFS'):
            try:
                version = _n.zpool_version(vol.vol_name)
            except:
                continue

            if vol.is_upgraded != True:
                alerts.append(Alert(
                    Alert.WARN,
                    _('You need to upgrade the volume %s') % vol.vol_name,
                ))

        return alerts

alertPlugins.register(VolumeVersionAlert)
