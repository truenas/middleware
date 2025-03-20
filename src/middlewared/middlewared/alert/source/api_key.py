from datetime import timedelta

from middlewared.alert.base import Alert, AlertClass, SimpleOneShotAlertClass, AlertCategory, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule


class ApiKeyRevokedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "API Key Revoked"
    text = (
        "%(name)s: API key has been revoked and must either be renewed or deleted. "
        "Revoke reason: %(reason)s. "
        "Once the maintenance is complete, API client configuration must be updated to "
        "use the renewed API key."
    )


class ApiKeyRevokedAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=1))

    async def check(self):
        alerts = []
        for key in await self.middleware.call("api_key.query"):
            if key["revoked"]:
                alerts.append(Alert(ApiKeyRevokedAlertClass, {
                    "name": key["name"],
                    "reason": key["revoked_reason"],
                }))

        return alerts
