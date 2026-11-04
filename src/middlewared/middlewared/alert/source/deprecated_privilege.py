from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertClassConfig, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.role import BUILTIN_GROUP_ROLES


@dataclass(kw_only=True)
class DeprecatedCustomPrivilegeAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SECURITY,
        level=AlertLevel.WARNING,
        title="Custom Privilege Set Is Deprecated",
        text=(
            "Privilege %(name)r grants %(roles)s. Using custom privilege sets is deprecated and will be removed in "
            "TrueNAS 28. Delete the privilege to clear this alert."
        ),
    )

    name: str
    roles: str


class DeprecatedCustomPrivilegeAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(days=1))

    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        alerts: list[Alert[Any]] = []
        for privilege in await self.middleware.call("datastore.query", "account.privilege"):
            if deprecated := set(privilege["roles"]) - BUILTIN_GROUP_ROLES:
                alerts.append(
                    Alert(
                        DeprecatedCustomPrivilegeAlert(
                            name=privilege["name"],
                            roles=", ".join(sorted(deprecated)),
                        )
                    )
                )

        return alerts
