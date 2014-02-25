import os

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert

class Samba4Alert(BaseAlert):
    def run(self):
        if os.path.exists('/var/db/samba4/.alert_cant_migrate'):
            return [
                Alert(
                    Alert.WARN,
                    'Multiple .samba4 datasets exist, unable to migrate, ' + 
                    'please migrate manually then remove /var/db/samba4/.alert_cant_migrate'
                ),
            ]


alertPlugins.register(Samba4Alert)
