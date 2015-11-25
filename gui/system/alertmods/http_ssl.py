import os
import glob
from django.utils.translation import ugettext as _


from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class SSLAlert(BaseAlert):

    interval = 5

    def run(self):
        alerts = []
        if os.path.exists('/tmp/alert_invalid_ssl_nginx'):
            msg = 'HTTP SSL certificate is not valid, failling back to HTTP'
            try:
                open('/tmp/alert_invalid_ssl_nginx').read().split()[0]
                msg = 'FreeNAS does not support certificates with keys shorter than 1024 bits. HTTPS will not be enabled until a certificate having at least 1024 bit keylength is provided'
            except IndexError:
                pass
            alerts.append(Alert(Alert.WARN,
                                msg))
        for cert_name in glob.glob("/var/tmp/alert_invalidcert_*"):
            alerts.append(Alert(Alert.WARN, _(
                'The Certificate: %(cert_name)s is either malformed '
                'or invalid and cannot be used for any services. This '
                'Alert will remain here until the certificate is deleted'
            ) % {'cert_name': cert_name.split('_', 2)[-1]}))

        for CA_name in glob.glob("/var/tmp/alert_invalidCA_*"):
            alerts.append(Alert(Alert.WARN, _(
                'The Certificate Authority(CA): %(CA_name)s is either '
                'malformed or invalid and cannot be used for any services.'
                ' This Alert will remain here until the CA is deleted'
            ) % {'CA_name': CA_name.split('_', 2)[-1]}))
        return alerts

alertPlugins.register(SSLAlert)
