import shutil
from humanfriendly import format_size

from middlewared.alert.base import (AlertClass, AlertCategory, AlertLevel,
                                    Alert, ThreadedAlertSource, UnavailableException)


class ReportingDbAlertClass(AlertClass):
    category = AlertCategory.REPORTING
    level = AlertLevel.WARNING
    title = 'Reporting Database Size Exceeds Threshold'
    text = 'Reporting database used size %(used)s is larger than %(threshold)s.'


class ReportingDbAlertSource(ThreadedAlertSource):
    def check_sync(self):
        try:
            used = shutil.disk_usage('/var/db/collectd/rrd').used
        except FileNotFoundError:
            raise UnavailableException()

        threshold = 1073741824 + len(self.middleware.call_sync('disk.query')) * 1024 * 1024

        if used > threshold:
            # zfs list reports in kibi/mebi/gibi(bytes) but
            # format_size() calculates in kilo/mega/giga by default
            # so the report that we send the user needs to match
            # up with what zfs list reports as to not confuse anyone
            used = format_size(used, binary=True)
            threshold = format_size(threshold, binary=True)

            return Alert(ReportingDbAlertClass, {'used': used, 'threshold': threshold}, key=None)
