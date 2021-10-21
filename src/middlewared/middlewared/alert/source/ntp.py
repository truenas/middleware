from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule


class NTPOffsetAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Excessive NTP server offset"
    text = "%(remote)s : offset exceeds five minutes: %(offset)s."


class NTPNoPeersAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "No NTP peers"
    text = "There are no current NTP peers. Server clock may drift."


class NTPOffsetAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=12))
    run_on_backup_node = False

    async def check(self):
        try:
            peers = await self.middleware.call("system.ntpserver.peers", [("status", "$", "PEER")])
        except Exception:
            peers = []

        if not peers:
            return

        offset = peers[0]['offset']
        if offset < 300000:
            return

        return Alert(
            NTPOffsetAlertClass,
            {'offset': str(offset), 'remote': peers[0]['remote']},
        )


class NTPNoPeersAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=12))
    run_on_backup_node = False

    async def check(self):
        try:
            peers = await self.middleware.call("system.ntpserver.peers")
        except Exception:
            peers = []

        if not peers:
            return

        if any(filter(lambda x: x['status'].endswith('PEER'), peers)):
            return

        return Alert(NTPNoPeersAlertClass)
