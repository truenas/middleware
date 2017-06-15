import subprocess

from django.utils.translation import ugettext as _

from freenasUI.storage.models import Volume
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class VolumeVersionAlert(BaseAlert):

    interval = 5

    def run(self):
        alerts = []
        for vol in Volume.objects.all():
            if vol.is_upgraded is not True:
                alerts.append(Alert(
                    Alert.WARN, _(
                        'New feature flags are available for volume %s. Refer '
                        'to the "Upgrading a ZFS Pool" section of the User '
                        'Guide for instructions.'
                    ) % vol.vol_name,
                ))

        proc = subprocess.Popen(
            "zfs upgrade | grep FILESYSTEM",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf8',
        )
        output = proc.communicate()[0].strip(' ').strip('\n')
        if output:
            alerts.append(Alert(Alert.WARN, _(
                'ZFS filesystem version is out of date. Consider upgrading'
                ' using "zfs upgrade" command line.'
            )))

        return alerts

alertPlugins.register(VolumeVersionAlert)
