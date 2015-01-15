import os

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class SSLAlert(BaseAlert):

    interval = 5

    def run(self):
        if os.path.exists('/tmp/alert_invalid_ssl_nginx'):
            msg='HTTP SSL certificate is not valid, failling back to HTTP'
            try:
                a=open('/tmp/alert_invalid_ssl_nginx').read().split()[0]
                msg = 'FreeNAS does not support certificates with keys shorter than 1024 bits. HTTPS will not be enabled until a certificate having at least 1024 bit keylength is provided'
            except IndexError:
                pass
            return [
                Alert(
                    Alert.WARN,
                    msg
                ),
            ]

alertPlugins.register(SSLAlert)
