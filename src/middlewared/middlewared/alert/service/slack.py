from __future__ import annotations

import html
import json
from typing import Any

import html2text
import requests

from middlewared.alert.base import Alert, ThreadedAlertService
from middlewared.utils.network import INTERNET_TIMEOUT


class SlackAlertService(ThreadedAlertService):
    title = "Slack"

    def send_sync(self, alerts: list[Alert[Any]], gone_alerts: list[Alert[Any]], new_alerts: list[Alert[Any]]) -> None:
        r = requests.post(
            self.attributes["url"],
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "text": html.escape(self._format_alerts_sync(alerts, gone_alerts, new_alerts), quote=False),
            }),
            timeout=INTERNET_TIMEOUT,
        )
        r.raise_for_status()
