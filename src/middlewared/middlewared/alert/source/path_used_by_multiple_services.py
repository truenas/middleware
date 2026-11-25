from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertClassConfig, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule


@dataclass(kw_only=True)
class PathUsedByMultipleServicesAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="Path Is Used By Multiple Services Or Workloads",
        text=(
            "This path is used by multiple services or workloads: %(path)s is accessed by %(consumers)s. Directly "
            "exposing the same data to another operating-system environment can cause inconsistent data, application "
            "failures, permission changes, or data corruption."
        ),
    )

    path: str
    consumers: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args["path"]


class PathUsedByMultipleServicesAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(days=1))
    run_on_backup_node = False

    async def check(self) -> list[Alert[Any]]:
        conflicts = await self.call2(self.s.filesystem.compatibility.conflicts)
        return [
            Alert(PathUsedByMultipleServicesAlert(path=path, consumers=consumers))
            for path, consumers in conflicts.items()
        ]
