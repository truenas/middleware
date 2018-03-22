import json
import requests

from middlewared.alert.base import ThreadedAlertService, format_alerts
from middlewared.schema import Dict, Str


class MattermostAlertService(ThreadedAlertService):
    title = "Mattermost"

    schema = Dict(
        "mattermost_attributes",
        Str("cluster_name"),
        Str("url"),
        Str("username"),
        Str("password"),
        Str("team"),
        Str("channel"),
    )

    def send_sync(self, alerts, gone_alerts, new_alerts):
        r = requests.post(
            self.attributes["url"],
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "channel": self.attributes["channel"],
                "username": self.attributes["username"],
                "text": format_alerts(alerts, gone_alerts, new_alerts),
            }),
            timeout=15,
        )
        r.raise_for_status()
