import json
import requests

from middlewared.alert.base import ProThreadedAlertService, ellipsis
from middlewared.utils.network import INTERNET_TIMEOUT


class OpsGenieAlertService(ProThreadedAlertService):
    title = "OpsGenie"

    def create_alert(self, alert):
        r = requests.post(
            (self.attributes.get("api_url") or "https://api.opsgenie.com") + "/v2/alerts",
            headers={"Authorization": f"GenieKey {self.attributes['api_key']}",
                     "Content-type": "application/json"},
            data=json.dumps({
                "message": ellipsis(alert.formatted, 130),
                "alias": alert.uuid,
                "description": ellipsis(alert.formatted, 15000),
            }),
            timeout=INTERNET_TIMEOUT,
        )
        r.raise_for_status()

    def delete_alert(self, alert):
        r = requests.delete(
            (self.attributes.get("api_url") or "https://api.opsgenie.com") + "/v2/alerts/" + alert.uuid,
            params={"identifierType": "alias"},
            headers={"Authorization": f"GenieKey {self.attributes['api_key']}"},
            timeout=INTERNET_TIMEOUT,
        )
        r.raise_for_status()
