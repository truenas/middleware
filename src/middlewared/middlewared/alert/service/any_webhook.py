import requests

from middlewared.alert.base import ThreadedAlertService
from middlewared.schema import Dict, Str
from middlewared.utils.network import INTERNET_TIMEOUT

class AnyWebhookAlerteService(ThreadedAlertService):
    title = "AnyWebhook"

    schema = Dict(
        "AnyWebhook_attributes",
        Str("url", required=True, empty=False),
        Str("message_key", requierd=True, empty=False)
    )

    def send_sync(self, alerts, gone_alerts, new_alerts):
        r = requests.get(
            url=self.attributes["url"],
            params={
                self.attributes["message_key"]: self._format_alerts(alerts, gone_alerts, new_alerts)
            }
        )

        r.raise_for_status()
