from middlewared.rclone.base import BaseRcloneRemote


class OneDriveRcloneRemote(BaseRcloneRemote):
    name = "ONEDRIVE"
    title = "Microsoft OneDrive"

    fast_list = True

    rclone_type = "onedrive"

    credentials_oauth = True
    refresh_credentials = ["token"]
