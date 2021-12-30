import requests
import json
import html2text

from middlewared.alert.base import ThreadedAlertService
from middlewared.schema import Dict, Str
from middlewared.utils.network import INTERNET_TIMEOUT

class FreeTelecomAlerteService(ThreadedAlertService):
    title = "AnyWebhook"

    schema = Dict(
        "FreeTelecom_attributes",
        Str("user", requierd=True, empty=False),
        Str("pass", requierd=True, empty=False),
    )

    def send_sync(self, alerts, gone_alerts, new_alerts):
        
        r = requests.post(
            url = "https://smsapi.free-mobile.fr/sendmsg",
            data = json.dumps({
                    "user": self.attributes["user"],
                    "pass": self.attributes["pass"],
                    "msg": html2text.html2text(self._format_alerts(alerts, gone_alerts, new_alerts))
                }),
            timeout = INTERNET_TIMEOUT
        )
        
        r.raise_for_status()
