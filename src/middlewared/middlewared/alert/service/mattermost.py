import json
import requests

from middlewared.alert.base import ThreadedAlertService
from middlewared.schema import Dict, Str


class MattermostAlertService(ThreadedAlertService):
    title = "Mattermost"

    schema = Dict(
        "mattermost_attributes",
        Str("url", required=True, empty=False),
        Str("username", required=True, empty=False),
        Str("channel", default=""),
        Str("icon_url", default=""),
        strict=True,
    )

    def send_sync(self, alerts, gone_alerts, new_alerts):
        r = requests.post(
            self.attributes["url"],
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "username": self.attributes["username"],
                "channel": self.attributes["channel"],
                "icon_url": self.attributes["icon_url"],
                "text": self._format_alerts(alerts, gone_alerts, new_alerts),
            }),
            timeout=15,
        )
        r.raise_for_status()
