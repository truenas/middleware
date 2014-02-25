import os

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert

class Samba4Alert(BaseAlert):
    def run(self):
        if os.path.exists('/var/db/samba4/.alert_cant_migrate'):
            return [
                Alert(
                    Alert.WARN,

                    "Multiple legacy samba4 datasets detected. Auto-migration to " +
                    "${poolname}/.system/samba4 cannot be done. Please perform this step " +
                    "manually and then delete the now-obsolete samba4 datasets and " +
                    "/var/db/samba4/.alert_cant_migrate"
                ),
            ]


alertPlugins.register(Samba4Alert)
