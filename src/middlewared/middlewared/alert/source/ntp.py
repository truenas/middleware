from datetime import timedelta

from middlewared.alert.base import (Alert, AlertCategory, AlertClass,
                                    AlertLevel, AlertSource)
from middlewared.alert.schedule import IntervalSchedule


class NTPHealthCheckAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "NTP Health Check Failed"
    text = "NTP health check failed - %(reason)s"


class NTPHealthCheckAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=12))
    run_on_backup_node = False

    async def check(self):
        if (await self.middleware.call("system.time_info"))["uptime_seconds"] < 300:
            return

        try:
            peers = await self.middleware.call("system.ntpserver.peers")
        except Exception:
            self.middleware.logger.warning("Failed to retrieve peers.", exc_info=True)
            peers = []

        if not peers:
            return

        active_peer = [x for x in peers if x["active"]]
        if not active_peer:
            names = [{f'{x["mode"]}: {x["state"]} [{x["remote"]}]'} for x in peers]
            return Alert(NTPHealthCheckAlertClass, {'reason': f'No Active NTP peers: {names}'})

        peer = active_peer[0]
        if peer["offset"] < 300:
            return

        msg = f'{peer["remote"]} has an offset of {peer["offset"]}, which exceeds permitted value of 5 minutes.'
        return Alert(NTPHealthCheckAlertClass, {'reason': msg})
