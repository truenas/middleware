from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class PcloudRcloneRemote(BaseRcloneRemote):
    name = "PCLOUD"
    title = "pCloud"

    rclone_type = "pcloud"

    credentials_schema = [
        Str("client_id", title="OAuth Client ID", default=""),
        Str("client_secret", title="OAuth Client Secret", default=""),
        Str("token", title="Access Token", required=True, max_length=None),
    ]
    credentials_oauth = True
    refresh_credentials = ["token"]
