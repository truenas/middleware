import os

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class SSLAlert(BaseAlert):

    def run(self):
        if os.path.exists('/tmp/alert_invalid_ssl_nginx'):
            msg='HTTP SSL certificate is not valid, failling back to HTTP'
            try:
                a=open('/tmp/alert_invalid_ssl_nginx').read().split()[0]
                msg = 'A %s-bit certificate was found for the WebGUI. We do not support certificates below 1024-bit key lenghts' %a
            except IndexError:
                pass
            return [
                Alert(
                    Alert.WARN,
                    msg
                ),
            ]

alertPlugins.register(SSLAlert)
