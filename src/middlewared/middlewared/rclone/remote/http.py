from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class HTTPRcloneRemote(BaseRcloneRemote):
    name = "HTTP"
    title = "HTTP"

    readonly = True

    rclone_type = "http"

    credentials_schema = [
        Str("url", verbose="URL", required=True),
    ]
