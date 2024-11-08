from middlewared.rclone.base import BaseRcloneRemote


class BoxRcloneRemote(BaseRcloneRemote):
    name = "BOX"
    title = "Box"

    rclone_type = "box"

    credentials_oauth = True
    refresh_credentials = ["token"]
