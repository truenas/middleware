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
            reason = f'No Active NTP peers: {names}'
            if failing := await self._failing_nts_sources():
                reason += (
                    f'. NTS key establishment is failing for: {", ".join(failing)}. Check that TCP port 4460 is '
                    'reachable, that the server certificate is trusted and that the system clock is roughly correct, '
                    'or disable NTS for these servers'
                )
            return Alert(NTPHealthCheckAlert(reason=reason))

        peer = active_peer[0]
        # Either clock may be the one ahead, so the offset can be negative
        if abs(peer["offset"]) < 300:
            return None

        msg = f'{peer["remote"]} has an offset of {peer["offset"]}, which exceeds permitted value of 5 minutes.'
        return Alert(NTPHealthCheckAlert(reason=msg))

    async def _failing_nts_sources(self) -> list[str]:
        """Names of the NTS sources that hold no keys, sorted so that the alert text stays the same between runs."""
        try:
            sources = await self.call2(self.s.system.ntpserver.nts_authdata)
        except Exception:
            self.middleware.logger.warning('ntp: failed to retrieve NTS authentication data', exc_info=True)
            return []

        return sorted({source['name'] for source in sources if not source['key_length'] or not source['cookies']})
