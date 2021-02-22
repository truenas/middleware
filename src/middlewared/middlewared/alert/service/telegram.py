import json
import requests

from middlewared.alert.base import ThreadedAlertService
from middlewared.schema import Dict, Str, List, Int
from middlewared.utils.network import INTERNET_TIMEOUT


class TelegramAlertService(ThreadedAlertService):
    title = "Telegram"

    schema = Dict(
        "telegram_attributes",
        Str("bot_token", required=True, empty=False),
        List("chat_ids", empty=False, items=[Int("chat_id")]),
        strict=True,
    )

    def send_sync(self, alerts, gone_alerts, new_alerts):
        token = self.attributes["bot_token"]
        chat_ids = self.attributes["chat_ids"]
        for chat_id in chat_ids:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                headers={"Content-type": "application/json"},
                data=json.dumps({
                    "chat_id": chat_id,
                    "text": self._format_alerts(alerts, gone_alerts, new_alerts),
                    "parse_mode": "HTML",
                }),
                timeout=INTERNET_TIMEOUT,
            )
            r.raise_for_status()
