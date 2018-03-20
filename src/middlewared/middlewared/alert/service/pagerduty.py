import json
import requests

from middlewared.alert.base import ProThreadedAlertService, ellipsis
from middlewared.schema import Dict, Str


class PagerDutyAlertService(ProThreadedAlertService):
    title = "PagerDuty"

    schema = Dict(
        "pagerduty_attributes",
        Str("service_key"),
        Str("client_name"),
    )

    def create_alert(self, alert):
        r = requests.post(
            "https://events.pagerduty.com/generic/2010-04-15/create_event.json",
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "service_key": self.attributes["service_key"],
                "event_type": "trigger",
                "description": ellipsis(alert.formatted, 1024),
                "incident_key": self._alert_id(alert),
                "client": self.attributes["client_name"],
            }),
            timeout=15,
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
                "incident_key": self._alert_id(alert),
                "client": self.attributes["client_name"],
            }),
            timeout=15,
        )
        r.raise_for_status()
