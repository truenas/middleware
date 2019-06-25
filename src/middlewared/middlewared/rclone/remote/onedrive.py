from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class OneDriveRcloneRemote(BaseRcloneRemote):
    name = "ONEDRIVE"
    title = "Microsoft OneDrive"

    rclone_type = "onedrive"

    credentials_schema = [
        Str("client_id", verbose="OAuth Client ID", default=""),
        Str("client_secret", verbose="OAuth Client Secret", default=""),
        Str("token", verbose="Access Token", required=True),
        Str("drive_type", verbose="Drive Account Type", enum=["PERSONAL", "BUSINESS", "DOCUMENT_LIBRARY"], required=True),
        Str("drive_id", verbose="Drive ID", required=True),
    ]
    credentials_oauth = True
    refresh_credentials = ["token"]

    def get_task_extra(self, task):
        return dict(
            drive_type={
                "": "",
                "PERSONAL": "personal",
                "BUSINESS": "business",
                "DOCUMENT_LIBRARY": "documentLibrary"
            }[task["credentials"]["attributes"].get("drive_type", "")]
        )
