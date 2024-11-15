from middlewared.rclone.base import BaseRcloneRemote


class OneDriveRcloneRemote(BaseRcloneRemote):
    name = "ONEDRIVE"
    title = "Microsoft OneDrive"

    rclone_type = ""
