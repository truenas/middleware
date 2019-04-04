import humanfriendly
import psutil

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource, UnavailableException


class ReportingDbAlertClass(AlertClass):
    category = AlertCategory.REPORTING
    level = AlertLevel.WARNING
    title = 'Reporting Database Size Is Larger than 1 GiB'
    text = 'Reporting database size (%s) is larger than 1 GiB.'


class ReportingDbAlertSource(ThreadedAlertSource):
    def check_sync(self):
        rrd_size_alert_threshold = 1073741824

        try:
            used = psutil.disk_usage('/var/db/collectd/rrd').used
        except FileNotFoundError:
            raise UnavailableException()

        if used > rrd_size_alert_threshold:
            return Alert(ReportingDbAlertClass,
                         args=humanfriendly.format_size(used),
                         key=None)
