from typing_extensions import Required
import requests
from requests.api import post

from middlewared.alert.base import ThreadedAlertService
from middlewared.middlewared.schema import Bool
from middlewared.schema import Dict, Str
from middlewared.utils.network import INTERNET_TIMEOUT

class AnyWebhookAlerteService(ThreadedAlertService):
    title = "AnyWebhook"

    schema = Dict(
        "AnyWebhook_attributes",
        Str("url", requierd=True, empty=False),
        Str("message_key", requierd=True, empty=False),
        Str("const_data", requierd=False, empty=True),
        Bool("get_post", required=False)
    )

    def send_sync(self, alerts, gone_alerts, new_alerts):
        getPost = self.attributes["get_post"]

        if getPost == False:
            r = requests.get(
                url=self.attributes["url"],
                params={
                    self.attributes["message_key"]: self._format_alerts(alerts, gone_alerts, new_alerts)
                },
                timeout=INTERNET_TIMEOUT
            )
        else:
            datas = self.attributes["const_data"] + "&" + self.attributes["message_key"] + "=" + self._format_alerts(alerts, gone_alerts, new_alerts)
            r = requests.post(
                url=self.attributes["url"],
                data=datas,
                timeout=INTERNET_TIMEOUT
            )
        
        r.raise_for_status()
