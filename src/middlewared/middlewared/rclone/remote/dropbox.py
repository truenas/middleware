from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class DropboxRcloneRemote(BaseRcloneRemote):
    name = "DROPBOX"
    title = "Dropbox"

    rclone_type = "dropbox"

    credentials_schema = [
        Str("token", title="Access Token", required=True),
    ]
