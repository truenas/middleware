import json
import requests

from middlewared.alert.base import ProThreadedAlertService, ellipsis
from middlewared.schema import Dict, Str


class OpsGenieAlertService(ProThreadedAlertService):
    title = "OpsGenie"

    schema = Dict(
        "opsgenie_attributes",
        Str("cluster_name"),
        Str("api_key"),
    )

    def create_alert(self, alert):
        r = requests.post(
            "https://api.opsgenie.com/v2/alerts",
            headers={"Authorization": f"GenieKey {self.attributes['api_key']}",
                     "Content-type": "application/json"},
            data=json.dumps({
                "message": ellipsis(alert.formatted, 130),
                "alias": self._alert_id(alert),
                "description": ellipsis(alert.formatted, 15000),
            }),
            timeout=15,
        )
        r.raise_for_status()

    def delete_alert(self, alert):
        r = requests.delete(
            "https://api.opsgenie.com/v2/alerts/" + self._alert_id(alert),
            params={"identifierType": "alias"},
            headers={"Authorization": f"GenieKey {self.attributes['api_key']}"},
            timeout=15,
        )
        r.raise_for_status()
