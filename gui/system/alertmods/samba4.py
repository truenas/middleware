import os

from freenasUI.storage.models import Volume
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.system.models import Advanced


class Samba4Alert(BaseAlert):

    def run(self):
        if not Volume.objects.all().exists():
            return None
        advanced = Advanced.objects.all()[0]
        if not advanced.adv_system_pool:
            return [
                Alert(
                    Alert.WARN,
                    "No system pool configured, please configure one in "
                    "Settings->Advanced->System dataset pool"
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
                    % advanced.adv_system_pool
                ),
            ]


alertPlugins.register(Samba4Alert)
