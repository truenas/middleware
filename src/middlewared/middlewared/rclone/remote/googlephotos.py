from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class GooglePhotosRcloneRemote(BaseRcloneRemote):
    name = "GOOGLE_PHOTOS"
    title = "Google Photos"

    rclone_type = "googlephotos"

    credentials_schema = [
        Str("client_id", title="OAuth Client ID", default=""),
        Str("client_secret", title="OAuth Client Secret", default=""),
        Str("token", title="Access Token", required=True, max_length=None),
    ]
    credentials_oauth = True
    refresh_credentials = ["token"]
