from datetime import timedelta
import logging
from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource, SimpleOneShotAlertClass
from middlewared.alert.schedule import IntervalSchedule

log = logging.getLogger("audit_check_alertmod")


# -------------- OneShot Alerts ------------------
class AuditBackendSetupAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.AUDIT
    level = AlertLevel.ERROR
    title = "Audit Service Backend Failed"
    text = "Audit service failed backend setup: %(service)s. See /var/log/middlewared.log"


class AuditSetupAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.AUDIT
    level = AlertLevel.ERROR
    title = "Audit Service Setup Failed"
    text = "Audit service failed to complete setup. See /var/log/middlewared.log"


# --------------- Monitored Alerts ----------------
class AuditServiceHealthAlertClass(AlertClass):
    category = AlertCategory.AUDIT
    level = AlertLevel.ERROR
    title = "Audit Service Health Failure"
    text = "Failed to perform audit query: %(verrs)s"


class AuditServiceHealthAlertSource(AlertSource):
    '''
    Run simple query every 20 minutes as a heath check
    '''
    schedule = IntervalSchedule(timedelta(minutes=20))
    run_on_backup_node = False

    async def check(self):
        try:
            await self.middleware.call(
                'audit.query', {
                    "query-options": {"count": True}
                }
            )
        except Exception as e:
            return Alert(
                AuditServiceHealthAlertClass,
                {'verrs': str(e)},
                key=None
            )
