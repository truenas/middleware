from typing_extensions import Required
import requests
import json

from sqlalchemy.sql.sqltypes import Boolean

from middlewared.alert.base import ThreadedAlertService
from middlewared.middlewared.schema import Bool
from middlewared.schema import Dict, Str
from middlewared.utils.network import INTERNET_TIMEOUT

class AnyWebhookAlerteService(ThreadedAlertService):
    title = "AnyWebhook"

    schema = Dict(
        "AnyWebhook_attributes",
        Str("url", requierd=True, empty=False),
        Str("body_template", requierd=True, empty=False),
        Bool("get_or_post", required=False)
    )

    def send_sync(self, alerts, gone_alerts, new_alerts):
        url = self.attributes["url"]
        msg = self._format_alerts(alerts, gone_alerts, new_alerts)
        getorpost = self.attributes["get_post"]
        body = self.attributes["body_template"].replace("%msg", msg)

        if getorpost == False:
            r = requests.get(
                url = f"{url}?{body}",
                timeout = INTERNET_TIMEOUT
            )
        else:
            r = requests.post(
                url = f"{url}",
                data = f"{body}",
                headers={"Content-type": "application/json"},
                timeout = INTERNET_TIMEOUT
            )
        
        r.raise_for_status()
