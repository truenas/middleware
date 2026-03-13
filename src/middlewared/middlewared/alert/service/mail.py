from __future__ import annotations

from typing import Any

from middlewared.alert.base import Alert, AlertService
from middlewared.service_exception import NetworkActivityDisabled


class MailAlertService(AlertService):
    title = "Email"

    html = True

    async def send(self, alerts: list[Alert[Any]], gone_alerts: list[Alert[Any]], new_alerts: list[Alert[Any]]) -> None:
        if self.attributes["email"]:
            emails = [self.attributes["email"]]
        else:
            emails = await self.middleware.call("mail.local_administrators_emails")
            if not emails:
                return

        try:
            await self.middleware.call("mail.send", {
                "subject": "Alerts",
                "html": await self._format_alerts(alerts, gone_alerts, new_alerts),
                "to": emails,
            })
        except NetworkActivityDisabled:
            pass
