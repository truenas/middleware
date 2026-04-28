from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    AlertSource,
    UnavailableException,
)
from middlewared.alert.schedule import IntervalSchedule


@dataclass(kw_only=True)
class ZpoolCapacityNoticeAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.NOTICE,
        title="Pool Space Usage Is Above 85%",
        text="Space usage for pool '%(volume)s' is %(capacity)d%%.",
        proactive_support=True,
    )

    volume: str
    capacity: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return [args['volume']]


@dataclass(kw_only=True)
class ZpoolCapacityWarningAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.WARNING,
        title="Pool Space Usage Is Above 90%",
        text="Space usage for pool '%(volume)s' is %(capacity)d%%.",
        proactive_support=True,
    )

    volume: str
    capacity: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return [args['volume']]


@dataclass(kw_only=True)
class ZpoolCapacityCriticalAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.CRITICAL,
        title="Pool Space Usage Is Above 95%",
        text="Space usage for pool '%(volume)s' is %(capacity)d%%.",
        proactive_support=True,
    )

    volume: str
    capacity: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return [args['volume']]


class ZpoolCapacityAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))

    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        alerts: list[Alert[Any]] = []
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
                (95, ZpoolCapacityCriticalAlert),
                (90, ZpoolCapacityWarningAlert),
                (85, ZpoolCapacityNoticeAlert),
            ]:
                if capacity >= target_capacity:
                    alerts.append(
                        Alert(
                            klass(volume=pool["name"], capacity=capacity),
                        )
                    )
                    break
                elif capacity == target_capacity - 1:
                    # If pool capacity is 89%, 79%, 69%, leave the alert in its previous state.
                    # In other words, don't flap alert in case if pool capacity is oscilating around threshold value.
                    raise UnavailableException()

        return alerts
