from datetime import datetime

from middlewared.alert.base import AlertClass, SimpleOneShotAlertClass, AlertCategory, AlertLevel, Alert, AlertSource


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


class CertificateIsExpiringAlertSource(AlertSource):
    async def check(self):
        alerts = []

        for cert in await self.middleware.call(
            'certificate.query',
            [['certificate', '!=', None]]
        ) + await self.middleware.call('certificateauthority.query'):
            if cert['parsed']:
                diff = (datetime.strptime(cert['until'], '%a %b %d %H:%M:%S %Y') - datetime.utcnow()).days
                if diff < 10:
                    alerts.append(
                        Alert(
                            CertificateIsExpiringSoonAlertClass if diff <= 2 else CertificateIsExpiringAlertClass,
                            {
                                "name": cert["name"],
                                "days": diff,
                            },
                            key=[cert["name"]],
                        )
                    )

        return alerts


class CertificateParsingFailedAlertClass(AlertClass):
    category = AlertCategory.CERTIFICATES
    level = AlertLevel.WARNING
    title = "Certificate Parsing Failed"
    text = "Failed to parse %(type)s %(name)r."


class CertificateParsingFailedAlertSource(AlertSource):
    async def check(self):
        alerts = []

        for cert in await self.middleware.call(
                'certificate.query',
                [['certificate', '!=', None]]
        ) + await self.middleware.call('certificateauthority.query'):
            if not cert['parsed']:
                alerts.append(
                    Alert(
                        CertificateParsingFailedAlertClass,
                        {
                            "type": cert["cert_type"].capitalize(),
                            "name": cert["name"],
                        },
                    )
                )

        return alerts


class WebUiCertificateSetupFailedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.CERTIFICATES
    level = AlertLevel.CRITICAL
    title = "Web UI HTTPS Certificate Setup Failed"
    text = "Web UI HTTPS certificate setup failed."
