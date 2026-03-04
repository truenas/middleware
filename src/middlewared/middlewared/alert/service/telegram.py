from __future__ import annotations

import html
import json
from typing import Any

import html2text
import requests

from middlewared.alert.base import Alert, ThreadedAlertService
from middlewared.utils.network import INTERNET_TIMEOUT


class TelegramAlertService(ThreadedAlertService):
    title = "Telegram"

    def send_sync(self, alerts: list[Alert[Any]], gone_alerts: list[Alert[Any]], new_alerts: list[Alert[Any]]) -> None:
        token = self.attributes["bot_token"]
        chat_ids = self.attributes["chat_ids"]
        for chat_id in chat_ids:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                headers={"Content-type": "application/json"},
                data=json.dumps({
                    "chat_id": chat_id,
                    "text": html.escape(self._format_alerts_sync(alerts, gone_alerts, new_alerts)),
                    "parse_mode": "HTML",
                }),
                timeout=INTERNET_TIMEOUT,
            )
            r.raise_for_status()
