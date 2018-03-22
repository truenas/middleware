from datetime import timedelta
import glob
import os

from middlewared.alert.base import Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule


class HTTPD_SSL_AlertSource(AlertSource):
    level = AlertLevel.WARNING
    title = "FreeNAS HTTP server SSL misconfiguration"

    schedule = IntervalSchedule(timedelta(minutes=5))

    async def check(self):
        alerts = []

        if os.path.exists("/tmp/alert_invalid_ssl_nginx"):
            alerts.append(Alert(
                "FreeNAS does not support certificates with keys shorter than 1024 bits. "
                "HTTPS will not be enabled until a certificate having at least 1024 bit "
                "keylength is provided",
            ))

        for cert_name in glob.glob("/var/tmp/alert_invalidcert_*"):
            alerts.append(Alert(
                "The Certificate: %(cert_name)s is either malformed "
                "or invalid and cannot be used for any services. "
                "This Alert will remain here until the certificate is deleted",
                {"cert_name": cert_name.split("_", 2)[-1]},
            ))

        for CA_name in glob.glob("/var/tmp/alert_invalidCA_*"):
            alerts.append(Alert(
                "The Certificate Authority(CA): %(CA_name)s is either "
                "malformed or invalid and cannot be used for any services. "
                "This Alert will remain here until the CA is deleted",
                {"CA_name": CA_name.split("_", 2)[-1]},
            ))

        return alerts
