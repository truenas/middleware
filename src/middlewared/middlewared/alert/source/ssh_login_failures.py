from dataclasses import dataclass
from datetime import timedelta
from time import time
from typing import Any

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    AlertSource,
)
from middlewared.alert.schedule import IntervalSchedule


@dataclass(kw_only=True)
class SSHLoginFailuresAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="SSH Login Failures",
        text="%(cnt)d SSH login failures in the last 24 hours",
    )

    cnt: int


class SSHLoginFailuresAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=24))

    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        cnt = await self.middleware.call(
            "audit.query",
            {
                "services": ["SYSTEM"],
                "query-filters": [
                    # current time minus 24h in seconds
                    ["message_timestamp", ">=", int(time() - 86_400)],
                    ["success", "=", False],
                    ["event", "=", "CREDENTIAL"],
                    ["event_data.auth_action", "=", "USER_AUTH"],
                    ["event_data.terminal", "=", "ssh"],
                    ["event_data.function", "=", "PAM:authentication"],
                ],
                "query-options": {
                    "count": True,
                },
            },
        )
        if cnt > 0:
            return Alert(SSHLoginFailuresAlert(cnt=cnt))

        return None
