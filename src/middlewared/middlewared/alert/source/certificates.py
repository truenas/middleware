from datetime import datetime

from middlewared.alert.base import Alert, AlertLevel, AlertSource, OneShotAlertSource


class CertRenewalAlertSource(AlertSource):
    title = 'Certificate expiring'
    level = AlertLevel.INFO

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
                            title=f'{cert["name"]} expiring within {diff} days',
                            level=AlertLevel.CRITICAL if diff < 2 else AlertLevel.INFO,
                            key=[cert['name'], diff < 2]
                        )
                    )

        return alerts


class CertificateParsingFailedAlertSource(AlertSource):
    title = 'Certificate Invalid'
    level = AlertLevel.WARNING

    async def check(self):
        alerts = []

        for cert in await self.middleware.call(
                'certificate.query',
                [['certificate', '!=', None]]
        ) + await self.middleware.call('certificateauthority.query'):
            if not cert['parsed']:
                alerts.append(
                    Alert(
                        title=f'Failed to parse {cert["name"]} {cert["cert_type"].capitalize()}. This cannot be used '
                              'with any service and this alert will remain here until this is deleted',
                        level=AlertLevel.WARNING,
                        key=[cert['name'], cert['cert_type']]
                    )
                )

        return alerts


class NginxCertificateSetupFailedAlertSource(OneShotAlertSource):
    title = 'Nginx Certificate Setup Failed'
    level = AlertLevel.CRITICAL

    async def create(self, args):
        return Alert('Certificate setup failing for HTTPS to be enabled in nginx', key=None)

    async def delete(self, alerts, query):
        return []
