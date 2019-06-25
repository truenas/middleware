from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class WebDavRcloneRemote(BaseRcloneRemote):
    name = "YANDEX"
    title = "Yandex"

    rclone_type = "yandex"

    credentials_schema = [
        Str("client_id", verbose="OAuth Client ID", default=""),
        Str("client_secret", verbose="OAuth Client Secret", default=""),
        Str("token", verbose="Access Token", required=True),
    ]
    credentials_oauth = True
    refresh_credentials = ["token"]
