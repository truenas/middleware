import json
import requests

from middlewared.alert.base import ThreadedAlertService
from middlewared.schema import Dict, Str
from middlewared.utils.network import INTERNET_TIMEOUT


class SlackAlertService(ThreadedAlertService):
    title = "Slack"

    schema = Dict(
        "slack_attributes",
        Str("url", required=True, empty=False),
        strict=True,
    )

    def send_sync(self, alerts, gone_alerts, new_alerts):
        r = requests.post(
            self.attributes["url"],
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "text": self._format_alerts(alerts, gone_alerts, new_alerts),
            }),
            timeout=INTERNET_TIMEOUT,
        )
        r.raise_for_status()
