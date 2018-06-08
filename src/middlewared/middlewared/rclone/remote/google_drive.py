from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class GoogleDriveRcloneRemote(BaseRcloneRemote):
    name = "GOOGLE_DRIVE"
    title = "Google Drive"

    rclone_type = "drive"

    credentials_schema = [
        Str("token", verbose="Access Token", required=True),
    ]
