import errno
from datetime import timedelta

from middlewared.alert.base import (Alert, AlertCategory, AlertClass,
                                    AlertLevel, AlertSource,
                                    SimpleOneShotAlertClass)
from middlewared.alert.schedule import IntervalSchedule
from middlewared.plugins.ntp import NTPPeer
from middlewared.service_exception import CallError

ALLOWED_OFFSET_CLOCK_REALTIME = 120
ALLOWED_OFFSET_NTP = 300


class CtdbInitFailAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.CLUSTERING
    level = AlertLevel.WARNING
    title = "CTDB service initialization failed"
    text = "CTDB service initialization failed: %(errmsg)s"

    async def delete(self, alerts, query):
        return []


class CtdbClusteredServiceAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.CLUSTERING
    level = AlertLevel.WARNING
    title = "Clustered service start failed"
    text = "Clustered service start failed: %(errmsg)s"

    async def delete(self, alerts, query):
        return []


class ClusteredClockAlertClass(AlertClass):
    category = AlertCategory.CLUSTERING
    level = AlertLevel.WARNING
    title = "Clustered time consistency check failed"
    text = "%(errmsg)s"


class ClusteredClockOffsetAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=1))
    run_on_backup_node = False

    async def check(self):
        def get_clock_realtime(entry):
            return entry['clock_realtime']

        def get_offset(entry):
            return abs(NTPPeer(entry['ntp_peer']).offset_in_secs)

        if not await self.middleware.call('cluster.utils.is_clustered'):
            return

        if not await self.middleware.call('ctdb.general.healthy'):
            return

        if not await self.middleware.call('ctdb.general.is_rec_master'):
            return

        ips = await self.middleware.call('ctdb.private.ips.query')
        time_job = await self.middleware.call('cluster.utils.time_info')

        try:
            rv = await time_job.wait()
        except CallError:
            if errno == errno.ETIMEDOUT:
                errmsg = (
                    'Timed out waiting for responses from other nodes with time info.'
                    'This may indicate significant clock offsets between nodes and '
                    'require manual intervention to set clocks correctly.'
                )
                return Alert(
                    ClusteredClockAlertClass,
                    {'errmsg': errmsg},
                    key=None
                )

            self.logger.warning("Failed to retrieve time info from cluster", exc_info=True)
            return

        for idx, r in enumerate(rv.copy()):
            if r is None:
                rv.pop(idx)

        ntp_broken = [x for x in rv if x['ntp_peer'] is None]
        if ntp_broken:
            errmsg = (
                'The node(s) at the following address(es) are not properly reporting their time: '
                f'{", ".join(ips[x["node"]]["address"] for x in ntp_broken)}. The most '
                'likely cause is that ntpd is failing to start due to excessive clock '
                'offset between the node and the remote NTP server with which it is '
                'attempting to communicate.'
            )
            return Alert(
                ClusteredClockAlertClass,
                {'errmsg': errmsg},
                key=None
            )

        clock_high = max(rv, key=get_clock_realtime)
        clock_low = min(rv, key=get_clock_realtime)
        current_realtime_offset = clock_high['clock_realtime'] - clock_low['clock_realtime']

        if current_realtime_offset > ALLOWED_OFFSET_CLOCK_REALTIME:
            # We have to have a fudge factor because there may be some seconds delay
            # for all nodes returning their results. 5 minutes is sufficient to break
            # kerberos authentication, and so 2 minutes was selected as the canary.
            high_node = clock_high['pnn']
            low_node = clock_low['pnn']

            errmsg = (
                f'Time offset of {current_realtime_offset} between nodes at {ips[high_node["address"]]} '
                f'and {ips[low_node["address"]]} exceeds {ALLOWED_OFFSET_CLOCK_REALTIME} seconds'
            )

            return Alert(
                ClusteredClockAlertClass,
                {'errmsg': errmsg},
                key=None
            )

        worst_offset = max(rv, key=get_offset)
        if abs(NTPPeer(worst_offset['ntp_peer']).offset_in_secs) > ALLOWED_OFFSET_NTP:
            errmsg = f'NTP offset of node {ips[worst_offset["pnn"]]["address"]} exceeds 5 minutes.'
            return Alert(
                ClusteredClockAlertClass,
                {'errmsg': errmsg},
                key=None
            )
