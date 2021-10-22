from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule


class NTPHealthAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Excessive NTP server offset"
    text = "NTP health check failed: %(reason)"


class NTPHealthAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=12))
    run_on_backup_node = False

    async def check(self):
        try:
            peers = await self.middleware.call("system.ntpserver.peers", [("status", "$", "PEER")])
        except Exception:
            peers = []

        if not peers:
            return

        active_peer = filter(lambda x: x['status'].endswith('PEER'), peers)
        if not active_peer:
            return Alert(
                NTPHealthAlertClass,
                {'reason': 'no NTP peers'}
            )

        peer = active_peer[0]
        if peer['offset'] < 300000:
            return

        return Alert(
            NTPHealthAlertClass,
            {'reason': f'{peer["remote"]}: offset exceeds permitted value: {peer["offset"]}'}
        )
