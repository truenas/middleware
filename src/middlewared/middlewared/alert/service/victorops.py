from __future__ import annotations

import json
from typing import Any

import requests

from middlewared.alert.base import Alert, ProThreadedAlertService
from middlewared.api.current import VictorOpsServiceModel
from middlewared.utils.network import INTERNET_TIMEOUT


class VictorOpsAlertService(ProThreadedAlertService[VictorOpsServiceModel]):
    title = "VictorOps"

    def create_alert(self, alert: Alert[Any]) -> None:
        self._send_message("CRITICAL", alert)

    def delete_alert(self, alert: Alert[Any]) -> None:
        self._send_message("RECOVERY", alert)

    def _send_message(self, message_type: str, alert: Alert[Any]) -> None:
        r = requests.post(
            f"https://alert.victorops.com/integrations/generic/20131114/alert/"
            f"{self.attributes.api_key.get_secret_value()}/{self.attributes.routing_key}",
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "message_type": message_type,
                "entity_id": alert.uuid,
                "entity_display_name": alert.formatted,
                "state_message": alert.formatted,
            }),
            timeout=INTERNET_TIMEOUT,
        )
        r.raise_for_status()
