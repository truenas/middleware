import requests

from middlewared.alert.base import ThreadedAlertService
from middlewared.schema import Dict, Str


class TelegramAlertService(ThreadedAlertService):
    title = "Telegram"

    schema = Dict(
        "Telegram_attributes",
        Str("base_url", default="https://api.telegram.org/bot"),
        Str("TELEGRAM_CHAT_ID", required=True, empty=False),
        Str("TELEGRAM_BOT_TOKEN", required=True, empty=False),
        strict=True,
    )


    def send_sync(self, alerts, gone_alerts, new_alerts):
        url = {self.attributes["base_url"]} + {self.attributes['TELEGRAM_BOT_TOKEN']} + '/sendMessage'
        post_data = {"chat_id": {self.attributes['TELEGRAM_CHAT_ID']}, "text": self._format_alerts(alerts, gone_alerts, new_alerts), "parse_mode": "Markdown"}
        r = requests.post(
            url, data=post_data,
            timeout=15,
        )
        r.raise_for_status()
