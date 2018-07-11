import pytz

from datetime import datetime, timedelta, timezone

from middlewared.alert.base import Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule


# Maybe incorporate other certificates as well in this alert source
class ACMECertRenewalAlertSource(AlertSource):
    title = 'ACME certificate expiring'
    level = AlertLevel.INFO

    schedule = IntervalSchedule(timedelta(hours=1))

    async def check(self):
        alerts = []
        for cert in await self.middleware.call(
            'certificate.query', [['acme', '!=', None]]
        ):
            diff = (pytz.utc.localize(cert['expire']) - datetime.now(timezone.utc)).days
            if diff < 10:
                alerts.append(
                    Alert(
                        title=f'{cert["name"]} expiring within {diff} days',
                        level=AlertLevel.CRITICAL if diff < 2 else AlertLevel.INFO
                    )
                )
        return alerts
