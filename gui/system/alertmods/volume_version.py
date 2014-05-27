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

            if version != '-':
                alerts.append(Alert(
                    Alert.CRIT,
                    _('You need to upgrade the volume %s') % vol.vol_name,
                ))
            else:
                proc = subprocess.Popen([
                    "zpool",
                    "get",
                    "-H", "-o", "property,value",
                    "all",
                    str(vol.vol_name),
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                data = proc.communicate()[0].strip('\n')

                for line in data.split('\n'):
                    if not line.startswith('feature') or '\t' not in line:
                        continue
                    prop, value = line.split('\t', 1)
                    if value not in ('active', 'enabled'):
                        alerts.append(Alert(
                            Alert.WARN,
                            _(
                                'You need to upgrade the volume %s'
                            ) % vol.vol_name,
                        ))
                        break

        return alerts

alertPlugins.register(VolumeVersionAlert)
