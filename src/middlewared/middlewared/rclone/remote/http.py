from middlewared.rclone.base import BaseRcloneRemote


class HTTPRcloneRemote(BaseRcloneRemote):
    name = "HTTP"
    title = "HTTP"

    readonly = True

    rclone_type = "http"
