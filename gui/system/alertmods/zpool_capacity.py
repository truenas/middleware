import logging
import subprocess

from django.utils.translation import ugettext as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.storage.models import Volume

log = logging.getLogger('system.alertmods.zpool_capacity')


class ZpoolCapAlert(BaseAlert):

    interval = 5

    def run(self):
        alerts = []
        pools = [
            vol.vol_name
            for vol in Volume.objects.all()
        ] + ['freenas-boot']
        for pool in pools:
            proc = subprocess.Popen([
                "/sbin/zpool",
                "list",
                "-H",
                "-o", "cap",
                pool.encode('utf8'),
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
            data = proc.communicate()[0]
            if proc.returncode != 0:
                continue
            try:
                cap = int(data.strip('\n').replace('%', ''))
            except ValueError:
                continue

            msg = _(
                'The capacity for the volume \'%(volume)s\' is currently at '
                '%(capacity)d%%, while the recommended value is below 80%%.'
            )
            level = None
            if cap >= 90:
                level = Alert.CRIT
            elif cap >= 80:
                level = Alert.WARN
            if level:
                alerts.append(
                    Alert(
                        level,
                        msg % {
                            'volume': pool,
                            'capacity': cap,
                        },
                    )
                )
        return alerts

alertPlugins.register(ZpoolCapAlert)
