from middlewared.alert.base import AlertService, format_alerts
from middlewared.schema import Dict, Str


class MailAlertService(AlertService):
    title = "E-Mail"

    schema = Dict(
        "mail_attributes",
        Str("email")
    )

    async def send(self, alerts, gone_alerts, new_alerts):
        email = self.attributes["email"]
        if not email:
            email = (await self.middleware.call("user.query", [("username", "=", "root")], {"get": True}))["email"]
        if not email:
            self.logger.trace("E-Mail address for root not configured, not sending e-mail")
            return

        await self.middleware.call("mail.send", {
            "subject": "Alerts",
            "text": format_alerts(alerts, gone_alerts, new_alerts),
            "to": [email],
        })
