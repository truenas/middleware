from datetime import timedelta

from middlewared.alert.base import (
    AlertClass,
    AlertCategory,
    AlertClassConfig,
    AlertLevel,
    Alert,
    AlertSource,
    UnavailableException,
)
from middlewared.alert.schedule import IntervalSchedule


class ZpoolCapacityNoticeAlertClass(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.NOTICE,
        title="Pool Space Usage Is Above 85%",
        text="Space usage for pool '%(volume)s' is %(capacity)d%%.",
        proactive_support=True,
    )


class ZpoolCapacityWarningAlertClass(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.WARNING,
        title="Pool Space Usage Is Above 90%",
        text="Space usage for pool '%(volume)s' is %(capacity)d%%.",
        proactive_support=True,
    )


class ZpoolCapacityCriticalAlertClass(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.CRITICAL,
        title="Pool Space Usage Is Above 95%",
        text="Space usage for pool '%(volume)s' is %(capacity)d%%.",
        proactive_support=True,
    )


class ZpoolCapacityAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))

    async def check(self):
        alerts = []
        # query_impl with pool_names=None skips boot pools, so we query
        # the boot pool explicitly to ensure capacity alerts still fire.
        pools = await self.middleware.call("zpool.query_impl", {"properties": ["capacity"]})
        pools.extend(await self.middleware.call(
            "zpool.query_impl",
            {"pool_names": [await self.middleware.call("boot.pool_name")], "properties": ["capacity"]}
        ))
        for pool in pools:
            try:
                capacity = int(pool["properties"]["capacity"]["value"])
            except (KeyError, ValueError):
                continue

            for target_capacity, klass in [
                (95, ZpoolCapacityCriticalAlertClass),
                (90, ZpoolCapacityWarningAlertClass),
                (85, ZpoolCapacityNoticeAlertClass),
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
