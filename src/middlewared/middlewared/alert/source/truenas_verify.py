from datetime import timedelta
import subprocess

from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils.security import system_security_config_to_stig_type


# --------------- Monitored Alerts ----------------
class TrueNASVerifyServiceChangeDetectionAlertClass(AlertClass):
    category = AlertCategory.AUDIT
    level = AlertLevel.ERROR
    title = "TrueNAS Verify Service: Changes detected in root file system."
    text = "%(verrs)s"


class TrueNASVerifyServiceChangeDetectionAlertSource(ThreadedAlertSource):
    '''
    Periodic verification of root file system
    '''
    schedule = IntervalSchedule(timedelta(hours=24))
    run_on_backup_node = False

    def check_sync(self):
        # Run only if in stig mode
        if self.stig_enabled():
            # Capture the results in syslog
            res = subprocess.run(['truenas_verify', 'syslog'], capture_output=True, text=True)
            if res.returncode:
                errmsg = f"{res.stderr}  See syslog for details."
                return Alert(
                    TrueNASVerifyServiceChangeDetectionAlertClass,
                    {'verrs': errmsg},
                    key=None
                )

    def stig_enabled(self):
        security_config = self.middleware.call_sync('system.security.config')
        enabled_stig = system_security_config_to_stig_type(security_config)
        return enabled_stig
