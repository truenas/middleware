from datetime import datetime

from middlewared.alert.base import Alert, AlertLevel, AlertSource


class CertRenewalAlertSource(AlertSource):
    title = 'Certificate expiring'
    level = AlertLevel.INFO

    async def check(self):
        alerts = []

        for cert in await self.middleware.call(
            'certificate.query',
            [['certificate', '!=', None]]
        ) + await self.middleware.call('certificateauthority.query'):
            diff = (datetime.strptime(cert['until'], '%a %b %d %H:%M:%S %Y') - datetime.now()).days
            if diff < 10:
                alerts.append(
                    Alert(
                        title=f'{cert["name"]} expiring within {diff} days',
                        level=AlertLevel.CRITICAL if diff < 2 else AlertLevel.INFO
                    )
                )

        return alerts
