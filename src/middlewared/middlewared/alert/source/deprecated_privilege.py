from datetime import timedelta

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.role import BUILTIN_GROUP_ROLES


class DeprecatedCustomPrivilegeAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Custom Privilege Set Is Deprecated"
    text = (
        "Privilege %(name)r grants %(roles)s. Using custom privilege sets is deprecated and will be removed in "
        "TrueNAS 28. Delete the privilege to clear this alert."
    )


class DeprecatedCustomPrivilegeAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(days=1))

    async def check(self):
        alerts = []
        for privilege in await self.middleware.call("datastore.query", "account.privilege"):
            if deprecated := set(privilege["roles"]) - BUILTIN_GROUP_ROLES:
                args = {"name": privilege["name"], "roles": ", ".join(sorted(deprecated))}
                alerts.append(Alert(DeprecatedCustomPrivilegeAlertClass, args))

        return alerts
