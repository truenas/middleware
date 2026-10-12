from typing import Any

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    AlertSource,
)


class SyslogNgAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.REPORTING,
        level=AlertLevel.WARNING,
        title="syslog-ng Is Not Running",
        text="The syslog-ng service is not running. The system does not record log messages or audit events.",
    )


class SyslogNgAlertSource(AlertSource):
    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        if await self.call2(self.s.service.started, "syslogd"):
            return None

        return Alert(SyslogNgAlert())
