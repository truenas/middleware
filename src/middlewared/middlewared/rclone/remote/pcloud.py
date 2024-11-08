from middlewared.rclone.base import BaseRcloneRemote


class PcloudRcloneRemote(BaseRcloneRemote):
    name = "PCLOUD"
    title = "pCloud"

    rclone_type = "pcloud"

    credentials_oauth = True
    credentials_oauth_name = "pcloud2"
    refresh_credentials = ["token"]
