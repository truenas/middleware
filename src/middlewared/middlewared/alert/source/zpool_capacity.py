from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource, UnavailableException
from middlewared.alert.schedule import IntervalSchedule


class ZpoolCapacityNoticeAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.NOTICE
    title = "Pool Space Usage Is Above 70%"
    text = (
        "Space usage for pool \"%(volume)s\" is %(capacity)d%%. "
        "Optimal pool performance requires used space remain below 80%%."
    )

    proactive_support = True


class ZpoolCapacityWarningAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "Pool Space Usage Is Above 80%"
    text = (
        "Space usage for pool \"%(volume)s\" is %(capacity)d%%. "
        "Optimal pool performance requires used space remain below 80%%."
    )

    proactive_support = True


class ZpoolCapacityCriticalAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.CRITICAL
    title = "Pool Space Usage Is Above 90%"
    text = (
        "Space usage for pool \"%(volume)s\" is %(capacity)d%%. "
        "Optimal pool performance requires used space remain below 80%%."
    )

    proactive_support = True


class ZpoolCapacityAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))

    async def check(self):
        alerts = []
        for pool in await self.middleware.call("zfs.pool.query"):
            try:
                capacity = int(pool["properties"]["capacity"]["parsed"])
            except (KeyError, ValueError):
                continue

            for target_capacity, klass in [
                (90, ZpoolCapacityCriticalAlertClass),
                (80, ZpoolCapacityWarningAlertClass),
                (70, ZpoolCapacityNoticeAlertClass),
            ]:
                if capacity >= target_capacity:
                    alerts.append(
                        Alert(
                            klass,
                            {
                                "volume": pool["name"],
                                "capacity": capacity,
                            },
                            key=[pool["name"]],
                        )
                    )
                    break
                elif capacity == target_capacity - 1:
                    # If pool capacity is 89%, 79%, 69%, leave the alert in its previous state.
                    # In other words, don't flap alert in case if pool capacity is oscilating around threshold value.
                    raise UnavailableException()

        return alerts
