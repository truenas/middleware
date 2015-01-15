from django.utils.translation import ugettext as _

from freenasUI.storage.models import Volume
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class VolumeVersionAlert(BaseAlert):

    interval = 5

    def run(self):
        alerts = []
        for vol in Volume.objects.filter(vol_fstype='ZFS'):
            if vol.is_upgraded is not True:
                alerts.append(Alert(
                    Alert.WARN, _(
                        'New feature flags are available for volume %s. Refer '
                        'to the "Upgrading a ZFS Pool" section of the User '
                        'Guide for instructions.'
                    ) % vol.vol_name,
                ))

        return alerts

alertPlugins.register(VolumeVersionAlert)
