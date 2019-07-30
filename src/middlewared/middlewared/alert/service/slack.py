import json
import requests

from middlewared.alert.base import ThreadedAlertService
from middlewared.schema import Dict, Str


class SlackAlertService(ThreadedAlertService):
    title = "Slack"

    schema = Dict(
        "slack_attributes",
        Str("cluster_name"),
        Str("url"),
        Str("channel"),
        Str("username"),
        Str("icon_url"),
    )

    def send_sync(self, alerts, gone_alerts, new_alerts):
        r = requests.post(
            self.attributes["url"],
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "channel": self.attributes["channel"],
                "username": self.attributes["username"],
                "icon_url": self.attributes["icon_url"],
                "text": self._format_alerts(alerts, gone_alerts, new_alerts),
            }),
            timeout=15,
        )
        r.raise_for_status()
