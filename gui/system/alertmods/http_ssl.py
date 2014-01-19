import os

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class SSLAlert(BaseAlert):

    def run(self):
        if os.path.exists('/tmp/alert_invalid_ssl_nginx'):
            return [
                Alert(
                    Alert.WARN,
                    'HTTP SSL certificate is not valid, failling back to HTTP'
                ),
            ]

alertPlugins.register(SSLAlert)
