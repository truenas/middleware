import hashlib
import json
import requests

from middlewared.alert.base import ThreadedAlertService
from middlewared.schema import Dict, Str


class OpsGenieAlertService(ThreadedAlertService):
    title = "OpsGenie"

    schema = Dict(
        "opsgenie_attributes",
        Str("cluster_name"),
        Str("api_key"),
    )

    def _alert_alias(self, alert):
        return hashlib.sha256(json.dumps([alert.source, alert.key]).encode("utf-8")).hexdigest()

    def send_sync(self, alerts, gone_alerts, new_alerts):
        exc = None

        for alert in gone_alerts:
            try:
                r = requests.delete(
                    "https://api.opsgenie.com/v2/alerts/" + self._alert_alias(alert),
                    params={"identifierType": "alias"},
                    headers={"Authorization": f"GenieKey {self.attributes['api_key']}"},
                    timeout=15,
                )
                r.raise_for_status()
            except Exception as e:
                self.logger.warning("An exception occurred while deleting alert", exc_info=True)
                exc = e

        for alert in new_alerts:
            try:
                r = requests.post(
                    "https://api.opsgenie.com/v2/alerts",
                    headers={"Authorization": f"GenieKey {self.attributes['api_key']}",
                             "Content-type": "application/json"},
                    data=json.dumps({
                        "message": alert.formatted[:129] + ("…" if len(alert.formatted) > 129 else ""),
                        "alias": self._alert_alias(alert),
                        "description": alert.formatted[:15000],
                    }),
                    timeout=15,
                )
                r.raise_for_status()
            except Exception as e:
                self.logger.warning("An exception occurred while creating alert", exc_info=True)
                exc = e

        if exc is not None:
            raise exc
