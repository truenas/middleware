from datetime import datetime

from middlewared.alert.base import AlertClass, SimpleOneShotAlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.alert.schedule import CrontabSchedule
from middlewared.utils.time_utils import utc_now


class CertificateIsExpiringAlertClass(AlertClass):
    category = AlertCategory.CERTIFICATES
    level = AlertLevel.NOTICE
    title = "Certificate Is Expiring"
    text = "Certificate %(name)r is expiring within %(days)d days."


class CertificateIsExpiringSoonAlertClass(AlertClass):
    category = AlertCategory.CERTIFICATES
    level = AlertLevel.WARNING
    title = "Certificate Is Expiring Soon"
    text = "Certificate %(name)r is expiring within %(days)d days."


class CertificateExpiredAlertClass(AlertClass):
    category = AlertCategory.CERTIFICATES
    level = AlertLevel.CRITICAL
    title = "Certificate Has Expired"
    text = "Certificate %(name)r has expired."


class CertificateParsingFailedAlertClass(AlertClass):
    category = AlertCategory.CERTIFICATES
    level = AlertLevel.WARNING
    title = "Certificate Parsing Failed"
    text = "Failed to parse %(type)s %(name)r."


class WebUiCertificateSetupFailedAlertClass(AlertClass, SimpleOneShotAlertClass):
    # this is consumed in nginx.conf in the etc plugin
    # you don't have to specify the `AlertClass` verbiage
    # of the class name when calling it
    category = AlertCategory.CERTIFICATES
    level = AlertLevel.CRITICAL
    title = "Web UI HTTPS Certificate Setup Failed"
    text = "Web UI HTTPS certificate setup failed."


class CertificateChecksAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=0)  # every 24 hours
    run_on_backup_node = False

    async def _get_service_certs(self):
        _type = 'certificate'
        service_certs = [
            {
                'id': (await self.middleware.call('ftp.config'))['ssltls_certificate'],
                'service': 'FTP',
                'type': _type,
            },
            {
                'id': (await self.middleware.call('system.general.config'))['ui_certificate']['id'],
                'service': 'Web UI',
                'type': _type,
            },
            {
                'id': (await self.middleware.call('system.advanced.config'))['syslog_tls_certificate'],
                'service': 'Syslog',
                'type': _type,
            },
        ]
        return service_certs

    async def check(self):
        alerts = []

        # system certs
        certs = await self.middleware.call('certificate.query', [['certificate', '!=', None]])

        # service certs
        check_for_revocation = await self._get_service_certs()

        for cert in certs:
            # make the sure certs have been parsed correctly
            if not cert['parsed']:
                alerts.append(Alert(
                    CertificateParsingFailedAlertClass,
                    {"type": cert["cert_type"].capitalize(), "name": cert["name"]},
                ))
            else:
                # check the parsed certificate(s) for expiration
                if cert['cert_type'].capitalize() == 'CERTIFICATE':
                    diff = (datetime.strptime(cert['until'], '%a %b %d %H:%M:%S %Y') - utc_now()).days
                    if diff < 10:
                        if diff >= 0:
                            alerts.append(Alert(
                                CertificateIsExpiringSoonAlertClass if diff <= 2 else CertificateIsExpiringAlertClass,
                                {'name': cert['name'], 'days': diff}, key=[cert['name']],
                            ))
                        else:
                            alerts.append(Alert(
                                CertificateExpiredAlertClass,
                                {'name': cert['name']}, key=[cert['name']]
                            ))

        return alerts
