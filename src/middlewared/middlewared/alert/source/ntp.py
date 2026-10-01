from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertClassConfig, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule


@dataclass(kw_only=True)
class NTPHealthCheckAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="NTP Health Check Failed",
        text="NTP health check failed - %(reason)s",
    )

    reason: str


class NTPHealthCheckAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=12))
    run_on_backup_node = False

    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        if (await self.middleware.call("system.time_info"))["uptime_seconds"] < 300:
            return None

        try:
            peers = await self.middleware.call("system.ntpserver.peers")
        except Exception:
            self.middleware.logger.warning("Failed to retrieve peers.", exc_info=True)
            peers = []

        if not peers:
            return None

        active_peer = [x for x in peers if x["active"]]
        if not active_peer:
            names = [{f'{x["mode"]}: {x["state"]} [{x["remote"]}]'} for x in peers]
            return Alert(NTPHealthCheckAlert(reason=f'No Active NTP peers: {names}'))

        peer = active_peer[0]
        if peer["offset"] < 300:
            return None

        msg = f'{peer["remote"]} has an offset of {peer["offset"]}, which exceeds permitted value of 5 minutes.'
        return Alert(NTPHealthCheckAlert(reason=msg))
