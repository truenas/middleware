import textwrap

from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Bool, Str


class GoogleDriveRcloneRemote(BaseRcloneRemote):
    name = "GOOGLE_DRIVE"
    title = "Google Drive"

    fast_list = True

    rclone_type = "drive"

    credentials_schema = [
        Str("client_id", title="OAuth Client ID", default=""),
        Str("client_secret", title="OAuth Client Secret", default=""),
        Str("token", title="Access Token", required=True, max_length=None),
        Str("team_drive", title="Team Drive ID (if connecting to Team Drive)"),
    ]
    credentials_oauth = True
    refresh_credentials = ["token"]

    task_schema = [
        Bool("acknowledge_abuse",
             title="Allow files which return cannotDownloadAbusiveFile to be downloaded.",
             description=textwrap.dedent("""\
                If downloading a file returns the error "This file has been identified as malware or spam and cannot be
                downloaded" with the error code "cannotDownloadAbusiveFile" then enable this flag to indicate you
                acknowledge the risks of downloading the file and TrueNAS will download it anyway.
        """), default=False),
    ]

    async def get_credentials_extra(self, credentials):
        if credentials["attributes"].get("team_drive"):
            return dict()

        return dict(root_folder_id="root")
