import os

from freenasUI.middleware.client import client
from freenasUI.middleware.notifier import notifier
from freenasUI.storage.models import Volume
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class Samba4Alert(BaseAlert):

    def run(self):
        if not Volume.objects.all().exists():
            return None
        if (
            hasattr(notifier, 'failover_status') and
            notifier().failover_status() == 'BACKUP'
        ):
            return None
        with client as c:
            systemdataset = c.call('systemdataset.config')
        if not systemdataset['pool']:
            return [
                Alert(
                    Alert.WARN,
                    "No system pool configured, please configure one in "
                    "Settings->System Dataset->Pool"
                ),
            ]

        if os.path.exists('/var/db/samba4/.alert_cant_migrate'):
            return [
                Alert(
                    Alert.WARN,
                    "Multiple legacy samba4 datasets detected. Auto-migration "
                    "to /mnt/%s/.system/samba4 cannot be done. Please perform "
                    "this step manually and then delete the now-obsolete "
                    "samba4 datasets and /var/db/samba4/.alert_cant_migrate"
                    % systemdataset['pool']
                ),
            ]


alertPlugins.register(Samba4Alert)
