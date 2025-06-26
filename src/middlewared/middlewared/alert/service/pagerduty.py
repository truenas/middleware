import json

import html2text
import requests

from middlewared.alert.base import ProThreadedAlertService, ellipsis
from middlewared.utils.network import INTERNET_TIMEOUT


class PagerDutyAlertService(ProThreadedAlertService):
    title = "PagerDuty"

    def create_alert(self, alert):
        r = requests.post(
            "https://events.pagerduty.com/generic/2010-04-15/create_event.json",
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "service_key": self.attributes["service_key"],
                "event_type": "trigger",
                "description": ellipsis(html2text.html2text(alert.formatted), 1024),
                "incident_key": alert.uuid,
                "client": self.attributes["client_name"],
            }),
            timeout=INTERNET_TIMEOUT,
        )
        r.raise_for_status()

    def delete_alert(self, alert):
        r = requests.post(
            "https://events.pagerduty.com/generic/2010-04-15/create_event.json",
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "service_key": self.attributes["service_key"],
                "event_type": "resolve",
                "description": "",
                "incident_key": alert.uuid,
                "client": self.attributes["client_name"],
            }),
            timeout=INTERNET_TIMEOUT,
        )
        r.raise_for_status()
