from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    AlertSource,
    OneShotAlertClass,
)
from middlewared.alert.schedule import IntervalSchedule

log = logging.getLogger("audit_check_alertmod")


# -------------- OneShot Alerts ------------------
@dataclass(kw_only=True)
class AuditBackendSetupAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.AUDIT,
        level=AlertLevel.ERROR,
        title="Audit Service Backend Failed",
        text="Audit service failed backend setup: %(service)s. See /var/log/middlewared.log",
    )

    service: str


# --------------- Monitored Alerts ----------------
@dataclass(kw_only=True)
class AuditServiceHealthAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.AUDIT,
        level=AlertLevel.ERROR,
        title="Audit Service Health Failure",
        text="Failed to perform audit query: %(verrs)s",
    )

    verrs: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return None


class AuditServiceHealthAlertSource(AlertSource):
    """
    Run simple query every 20 minutes as a heath check
    """
    schedule = IntervalSchedule(timedelta(minutes=20))
    run_on_backup_node = False

    async def check(self) -> Alert[AuditServiceHealthAlert] | None:
        try:
            await self.middleware.call(
                "audit.query", {
                    "query-options": {"count": True}
                }
            )
        except Exception as e:
            return Alert(
                AuditServiceHealthAlert(verrs=str(e))
            )
        return None
