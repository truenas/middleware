from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Password, Str


class PcloudRcloneRemote(BaseRcloneRemote):
    name = "PCLOUD"
    title = "pCloud"

    rclone_type = "pcloud"

    credentials_schema = [
        Str("client_id", title="OAuth Client ID", default=""),
        Password("client_secret", title="OAuth Client Secret", default=""),
        Password("token", title="Access Token", required=True, max_length=None),
        Str("hostname", title="API hostname"),
    ]
    credentials_oauth = True
    credentials_oauth_name = "pcloud2"
    refresh_credentials = ["token"]
