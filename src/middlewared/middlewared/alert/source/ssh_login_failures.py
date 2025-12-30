import time

from middlewared.alert.base import (
    AlertClass,
    AlertCategory,
    AlertLevel,
    Alert,
    AlertSource,
)


class SSHLoginFailuresAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "SSH Login Failures"
    text = "%(cnt)d SSH login failures in the last 24 hours"


class SSHLoginFailuresAlertSource(AlertSource):
    async def check(self):
        cnt = await self.middleware.call(
            "audit.query",
            {
                "services": ["SYSTEM"],
                "query-filters": [
                    # current time minus 24h in seconds
                    ["message_timestamp", ">=", int(time.time() - 86_400)],
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
            return Alert(SSHLoginFailuresAlertClass, {"cnt": cnt})
