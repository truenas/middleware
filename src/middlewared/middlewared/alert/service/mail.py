from __future__ import annotations

from typing import Any

from middlewared.alert.base import Alert, AlertService
from middlewared.api.current import MailSendMessage, MailServiceModel
from middlewared.plugins.mail.config import sender_configured


class MailAlertService(AlertService[MailServiceModel]):
    title = "Email"

    html = True

    async def send(self, alerts: list[Alert[Any]], gone_alerts: list[Alert[Any]], new_alerts: list[Alert[Any]]) -> None:
        if self.attributes.email:
            emails = [self.attributes.email]
        else:
            emails = await self.middleware.call("mail.local_administrators_emails")
            if not emails:
                return

        if not sender_configured(await self.call2(self.s.mail.config)):
            return

        await self.call2(self.s.mail.send, MailSendMessage(
            subject="Alerts",
            html=await self._format_alerts(alerts, gone_alerts, new_alerts),
            to=emails,
        ))
