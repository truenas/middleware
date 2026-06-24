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


class AuditDatabaseCorruptedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.AUDIT
    level = AlertLevel.ERROR
    title = "Audit Database Contains Corrupted Records"
    text = (
        "The %(service)s audit database contains %(count)s record(s) with unreadable data "
        "that are skipped by audit queries. See /var/log/middlewared.log for details."
    )

    async def create(self, args):
        # Key on the service alone so a changing count updates the alert instead of duplicating it.
        return Alert(AuditDatabaseCorruptedAlertClass, args, key=args['service'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.args['service'] != query,
            alerts
        ))


# --------------- Monitored Alerts ----------------
class AuditServiceHealthAlertClass(AlertClass):
    category = AlertCategory.AUDIT
    level = AlertLevel.ERROR
    title = "Audit Service Health Failure"
    text = "Failed to perform audit query: %(verrs)s"


class AuditServiceHealthAlertSource(AlertSource):
    """
    Run simple query every 20 minutes as a heath check
    """
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
