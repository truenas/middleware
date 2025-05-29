import html
import json

import html2text
import requests

from middlewared.alert.base import ThreadedAlertService
from middlewared.utils.network import INTERNET_TIMEOUT


class SlackAlertService(ThreadedAlertService):
    title = "Slack"

    def send_sync(self, alerts, gone_alerts, new_alerts):
        r = requests.post(
            self.attributes["url"],
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "text": html.escape(
                    html2text.html2text(
                        self._format_alerts(
                            alerts, gone_alerts, new_alerts
                        )
                    ), quote=False
                ),
            }),
            timeout=INTERNET_TIMEOUT,
        )
        r.raise_for_status()
