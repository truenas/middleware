from __future__ import annotations

import html
import json
from typing import Any

import requests

from middlewared.alert.base import Alert, ThreadedAlertService
from middlewared.utils.network import INTERNET_TIMEOUT


class MattermostAlertService(ThreadedAlertService):
    title = "Mattermost"

    def send_sync(self, alerts: list[Alert[Any]], gone_alerts: list[Alert[Any]], new_alerts: list[Alert[Any]]) -> None:
        r = requests.post(
            self.attributes["url"],
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "username": self.attributes["username"],
                "channel": self.attributes["channel"],
                "icon_url": self.attributes["icon_url"],
                "text": html.escape(self._format_alerts_sync(alerts, gone_alerts, new_alerts)),
            }),
            timeout=INTERNET_TIMEOUT,
        )
        r.raise_for_status()
