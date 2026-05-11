from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass


class TimezoneNotAvailableAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Configured Timezone Not Available"
    text = (
        "The configured timezone %(timezone)r is not available on this system. "
        "The system clock has been set to UTC. Select a different timezone in "
        "System Settings -> General to clear this alert."
    )
    keys = []
