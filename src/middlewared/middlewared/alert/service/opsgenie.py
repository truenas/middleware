from __future__ import annotations

import json
from typing import Any

import requests

from middlewared.alert.base import Alert, ProThreadedAlertService, ellipsis
from middlewared.api.current import OpsGenieServiceModel
from middlewared.utils.network import INTERNET_TIMEOUT


class OpsGenieAlertService(ProThreadedAlertService[OpsGenieServiceModel]):
    title = "OpsGenie"

    @property
    def api_url(self) -> str:
        return self.attributes.api_url or "https://api.opsgenie.com"

    def create_alert(self, alert: Alert[Any]) -> None:
        r = requests.post(
            f"{self.api_url}/v2/alerts",
            headers={"Authorization": f"GenieKey {self.attributes.api_key.get_secret_value()}",
                     "Content-type": "application/json"},
            data=json.dumps({
                "message": ellipsis(alert.formatted, 130),
                "alias": alert.uuid,
                "description": ellipsis(alert.formatted, 15000),
            }),
            timeout=INTERNET_TIMEOUT,
        )
        r.raise_for_status()

    def delete_alert(self, alert: Alert[Any]) -> None:
        r = requests.delete(
            f"{self.api_url}/v2/alerts/{alert.uuid}",
            params={"identifierType": "alias"},
            headers={"Authorization": f"GenieKey {self.attributes.api_key.get_secret_value()}"},
            timeout=INTERNET_TIMEOUT,
        )
        r.raise_for_status()
