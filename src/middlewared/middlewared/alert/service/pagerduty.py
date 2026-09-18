from __future__ import annotations

import json
from typing import Any

import html2text
import requests

from middlewared.alert.base import Alert, ProThreadedAlertService, ellipsis
from middlewared.api.current import PagerDutyServiceModel
from middlewared.utils.network import INTERNET_TIMEOUT


class PagerDutyAlertService(ProThreadedAlertService[PagerDutyServiceModel]):
    title = "PagerDuty"

    def create_alert(self, alert: Alert[Any]) -> None:
        self._send_event("trigger", alert, ellipsis(html2text.html2text(alert.formatted), 1024))

    def delete_alert(self, alert: Alert[Any]) -> None:
        self._send_event("resolve", alert, "")

    def _send_event(self, event_type: str, alert: Alert[Any], description: str) -> None:
        r = requests.post(
            "https://events.pagerduty.com/generic/2010-04-15/create_event.json",
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "service_key": self.attributes.service_key.get_secret_value(),
                "event_type": event_type,
                "description": description,
                "incident_key": alert.uuid,
                "client": self.attributes.client_name,
            }),
            timeout=INTERNET_TIMEOUT,
        )
        r.raise_for_status()
