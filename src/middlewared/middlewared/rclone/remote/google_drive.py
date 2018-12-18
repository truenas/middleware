from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class GoogleDriveRcloneRemote(BaseRcloneRemote):
    name = "GOOGLE_DRIVE"
    title = "Google Drive"

    rclone_type = "drive"

    credentials_schema = [
        Str("client_id", verbose="OAuth Client ID", default=""),
        Str("client_secret", verbose="OAuth Client Secret", default=""),
        Str("token", verbose="Access Token", required=True),
        Str("team_drive", verbose="Team Drive ID (if connecting to Team Drive)"),
    ]
    credentials_oauth = True
    refresh_credentials = True
