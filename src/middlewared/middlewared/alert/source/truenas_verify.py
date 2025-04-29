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
    text = (
        "Root File System Verification reported %(verrs)s  Please see syslog for details regarding these files. '"
        "NOTE: Search syslog for messages from 'truenas_verify' and some descrepancies might be nominal."
    )


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
                return Alert(
                    TrueNASVerifyServiceChangeDetectionAlertClass,
                    {'verrs': res.stdout.strip()},
                    key=None
                )

    def stig_enabled(self):
        security_config = self.middleware.call_sync('system.security.config')
        enabled_stig = system_security_config_to_stig_type(security_config)
        return enabled_stig
