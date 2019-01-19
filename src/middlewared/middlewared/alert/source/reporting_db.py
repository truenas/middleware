import humanfriendly
import psutil

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource


class ReportingDbAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = 'Reporting database size is above specified threshold value'

    def check_sync(self):
        config = self.middleware.call_sync('reporting.config')
        rrd_size_alert_threshold = config['rrd_size_alert_threshold'] or config['rrd_size_alert_threshold_suggestion']

        used = psutil.disk_usage('/var/db/collectd/rrd').used
        if used > rrd_size_alert_threshold:
            return Alert('Reporting database size (%s) is above specified threshold value',
                         args=[humanfriendly.format_size(used)])
