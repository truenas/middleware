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
        Str("user_key", requierd=True, empty=False),
        Str("user_val", requierd=True, empty=False),
        Str("pass_key", requierd=True, empty=False),
        Str("pass_value", requierd=True, empty=False),
        Str("message_key", requierd=True, empty=False),
        Str("raw_key", requierd=False, empty=True),
        Str("raw_data", requierd=False, empty=True),
        Bool("get_post", required=False),
        Bool("json_body", requierd=False)
    )

    def send_sync(self, alerts, gone_alerts, new_alerts):
        alertMsg = self._format_alerts(alerts, gone_alerts, new_alerts)
        getPost = self.attributes["get_post"]
        jsonBody = self.attributes["json_body"]

        if getPost == False:
            r = requests.get(
                url=self.attributes["url"],
                params={
                    self.attributes["user_key"]: self.attributes["user_val"],
                    self.attributes["pass_key"]: self.attributes["pass_key"],
                    self.attributes["message_key"]: alertMsg,
                    self.attributes["raw_key"]: self.attributes["raw_data"]
                },
                timeout=INTERNET_TIMEOUT
            )
        else:
            if jsonBody == False:
                datas = self.attributes["user_key"] + "=" + self.attributes["user_val"] + "&" + self.attributes["pass_key"] + "=" + self.attributes["pass_key"] + "&" + self.attributes["message_key"] + "=" + alertMsg + "&" + self.attributes["raw_key"] + "=" + self.attributes["raw_data"]
            else:
                datas = json.dumps({
                    self.attributes["user_key"]: self.attributes["user_val"],
                    self.attributes["pass_key"]: self.attributes["pass_key"],
                    self.attributes["message_key"]: alertMsg,
                    self.attributes["raw_key"]: self.attributes["raw_data"]
                })

            r = requests.post(
                url=self.attributes["url"],
                data=datas,
                timeout=INTERNET_TIMEOUT
            )
        
        r.raise_for_status()
