from middlewared.alert.base import AlertService
from middlewared.service_exception import NetworkActivityDisabled


class MailAlertService(AlertService):
    title = "Email"

    html = True

    async def send(self, alerts, gone_alerts, new_alerts):
        if self.attributes["email"]:
            emails = [self.attributes["email"]]
        else:
            emails = await self.middleware.call("mail.local_administrators_emails")
            if not emails:
                self.logger.trace("No e-mail address configured for any of the local administrators, not sending email")
                return

        try:
            await self.middleware.call("mail.send", {
                "subject": "Alerts",
                "html": await self._format_alerts(alerts, gone_alerts, new_alerts),
                "to": emails,
            })
        except NetworkActivityDisabled:
            pass
