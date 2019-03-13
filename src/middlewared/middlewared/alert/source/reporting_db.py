import humanfriendly
import psutil

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource, UnavailableException


class ReportingDbAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = 'Reporting database size is above specified threshold value'

    def check_sync(self):
        rrd_size_alert_threshold = 1073741824

        try:
            used = psutil.disk_usage('/var/db/collectd/rrd').used
        except FileNotFoundError:
            raise UnavailableException()

        if used > rrd_size_alert_threshold:
            return Alert('Reporting database size (%s) is above 1 GiB',
                         args=[humanfriendly.format_size(used)])
