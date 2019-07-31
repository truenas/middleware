import json
import requests

from middlewared.alert.base import ThreadedAlertService
from middlewared.schema import Dict, Str


class HipChatAlertService(ThreadedAlertService):
    title = "HipChat"

    schema = Dict(
        "hipchat_attributes",
        Str("hfrom", required=True, empty=False),
        Str("cluster_name", default=""),
        Str("base_url", default=""),
        Str("room_id", required=True, empty=False),
        Str("auth_token", required=True, empty=False),
        strict=True,
    )

    def send_sync(self, alerts, gone_alerts, new_alerts):
        base_url = self.attributes["base_url"] or "https://api.hipchat.com"
        r = requests.post(
            f"{base_url}/v2/room/{self.attributes['room_id']}/notification",
            params={"auth_token": self.attributes["auth_token"]},
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "from": self.attributes["hfrom"],
                "message_format": "text",
                "message": self._format_alerts(alerts, gone_alerts, new_alerts),
            }),
            timeout=15,
        )
        r.raise_for_status()
