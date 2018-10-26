from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class OneDriveRcloneRemote(BaseRcloneRemote):
    name = "ONEDRIVE"
    title = "Microsoft OneDrive"

    rclone_type = "onedrive"

    credentials_schema = [
        Str("token", verbose="Access Token", required=True),
        Str("drive_type", verbose="Drive Type", enum=["PERSONAL", "BUSINESS", "DOCUMENT_LIBRARY"], required=True),
        Str("drive_id", verbose="Drive ID", required=True),
    ]

    def get_task_extra(self, task):
        return dict(
            drive_type={
                "": "",
                "PERSONAL": "personal",
                "BUSINESS": "business",
                "DOCUMENT_LIBRARY": "documentLibrary"
            }[task["credentials"]["attributes"].get("drive_type", "")]
        )
