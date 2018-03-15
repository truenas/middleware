import json
import requests

from middlewared.alert.base import ProThreadedAlertService
from middlewared.schema import Dict, Str


class VictorOpsAlertService(ProThreadedAlertService):
    title = "VictorOps"

    schema = Dict(
        "victorops_attributes",
        Str("api_key"),
        Str("routing_key"),
    )

    def create_alert(self, alert):
        r = requests.post(
            f"https://alert.victorops.com/integrations/generic/20131114/alert/{self.attributes['api_key']}/"
            f"{self.attributes['routing_key']}",
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "message_type": "CRITICAL",
                "entity_id": self._alert_id(alert),
                "entity_display_name": alert.formatted,
                "state_message": alert.formatted,
            }),
            timeout=15,
        )
        r.raise_for_status()

    def delete_alert(self, alert):
        r = requests.post(
            f"https://alert.victorops.com/integrations/generic/20131114/alert/{self.attributes['api_key']}/"
            f"{self.attributes['routing_key']}",
            headers={"Content-type": "application/json"},
            data=json.dumps({
                "message_type": "RECOVERY",
                "entity_id": self._alert_id(alert),
                "entity_display_name": alert.formatted,
                "state_message": alert.formatted,
            }),
            timeout=15,
        )
        r.raise_for_status()
