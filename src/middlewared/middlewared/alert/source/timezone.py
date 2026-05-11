from dataclasses import dataclass

from middlewared.alert.base import AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class TimezoneNotAvailableAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="Configured Timezone Not Available",
        text=(
            "The configured timezone %(timezone)r is not available on this system. "
            "The system clock has been set to UTC. Select a different timezone in "
            "System Settings -> General to clear this alert."
        ),
        keys=[],
    )

    timezone: str
