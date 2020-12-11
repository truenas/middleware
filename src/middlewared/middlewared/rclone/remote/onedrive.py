from datetime import datetime
import isodate
import json
import os

import bidict
import onedrivesdk
import onedrivesdk.session
import pytz

from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Dict, Str
from middlewared.service import accepts

DRIVES_TYPES = bidict.bidict({
    "PERSONAL": "personal",
    "BUSINESS": "business",
    "DOCUMENT_LIBRARY": "documentLibrary",
})


class RcloneTokenSession(onedrivesdk.session.Session):
    @staticmethod
    def load_session(**load_session_kwargs):
        client_id = load_session_kwargs["client_id"]
        client_secret = load_session_kwargs["client_secret"]
        token = json.loads(load_session_kwargs["token"])

        return RcloneTokenSession(
            token["token_type"],
            (datetime.now(pytz.timezone(os.environ["TZ"])) - isodate.parse_datetime(token["expiry"])).total_seconds(),
            token["scope"],
            token["access_token"],
            client_id,
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            None,
            token["refresh_token"],
            client_secret,
        )


class OneDriveRcloneRemote(BaseRcloneRemote):
    name = "ONEDRIVE"
    title = "Microsoft OneDrive"

    rclone_type = "onedrive"

    credentials_schema = [
        Str("client_id", title="OAuth Client ID", default=""),
        Str("client_secret", title="OAuth Client Secret", default=""),
        Str("token", title="Access Token", required=True, max_length=None),
        Str("drive_type", title="Drive Account Type", enum=list(DRIVES_TYPES.keys()), required=True),
        Str("drive_id", title="Drive ID", required=True),
    ]
    credentials_oauth = True
    refresh_credentials = ["token"]

    extra_methods = ["list_drives"]

    async def get_task_extra(self, task):
        return dict(
            drive_type=DRIVES_TYPES.get(task["credentials"]["attributes"]["drive_type"], ""),
        )

    @accepts(Dict(
        "onedrive_list_drives",
        Str("client_id", default=""),
        Str("client_secret", default=""),
        Str("token", required=True, max_length=None),
    ))
    def list_drives(self, credentials):
        """
        Lists all available drives and their types for given Microsoft OneDrive credentials.

        .. examples(websocket)::

            :::javascript
            {
              "id": "6841f242-840a-11e6-a437-00e04d680384",
              "msg": "method",
              "method": "cloudsync.onedrive_list_drives",
              "params": [{
                "client_id": "...",
                "client_secret": "",
                "token": "{...}",
              }]
            }

        Returns

            [{"drive_type": "PERSONAL", "drive_id": "6bb903a25ad65e46"}]
        """
        self.middleware.call_sync("network.general.will_perform_activity", "cloud_sync")

        if not credentials["client_id"]:
            credentials["client_id"] = "b15665d9-eda6-4092-8539-0eec376afd59"
        if not credentials["client_secret"]:
            credentials["client_secret"] = "qtyfaBBYA403=unZUP40~_#"

        http_provider = onedrivesdk.HttpProvider()
        auth_provider = onedrivesdk.AuthProvider(http_provider, session_type=RcloneTokenSession, loop=object())
        auth_provider.load_session(**credentials)
        auth_provider.refresh_token()

        client = onedrivesdk.OneDriveClient("https://graph.microsoft.com/v1.0/", auth_provider, http_provider, loop=object())
        result = []
        for drive in client.drives.get().drives():
            result.append({
                "drive_type": DRIVES_TYPES.inverse.get(drive.drive_type, ""),
                "drive_id": drive.id,
            })
        return result
