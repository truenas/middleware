from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Password, Str


class BoxRcloneRemote(BaseRcloneRemote):
    name = "BOX"
    title = "Box"

    rclone_type = "box"

    credentials_schema = [
        Str("client_id", title="OAuth Client ID", default=""),
        Password("client_secret", title="OAuth Client Secret", default=""),
        Password("token", title="Access Token", required=True, max_length=None),
    ]
    credentials_oauth = True
    refresh_credentials = ["token"]
