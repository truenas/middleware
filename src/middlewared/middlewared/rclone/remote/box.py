from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class BoxRcloneRemote(BaseRcloneRemote):
    name = "BOX"
    title = "Box"

    rclone_type = "box"

    credentials_schema = [
        Str("client_id", title="OAuth Client ID", default=""),
        Str("client_secret", title="OAuth Client Secret", default=""),
        Str("token", title="Access Token", required=True, max_length=None),
    ]
    credentials_oauth = True
    refresh_credentials = ["token"]
