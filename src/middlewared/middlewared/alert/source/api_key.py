from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertClassConfig, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule


@dataclass(kw_only=True)
class ApiKeyRevokedAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="API Key Revoked",
        text=(
            "%(name)s: API key has been revoked and must either be renewed or deleted. "
            "Revoke reason: %(reason)s. "
            "Once the maintenance is complete, API client configuration must be updated to "
            "use the renewed API key."
        ),
    )

    name: str
    reason: str


class ApiKeyRevokedAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=1))

    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        alerts: list[Alert[Any]] = []
        for key in await self.middleware.call("api_key.query"):
            if key["revoked"]:
                alerts.append(Alert(ApiKeyRevokedAlert(
                    name=key["name"],
                    reason=key["revoked_reason"],
                )))

        return alerts
