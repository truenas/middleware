from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class WebDavRcloneRemote(BaseRcloneRemote):
    name = "YANDEX"
    title = "Yandex"

    rclone_type = "yandex"

    credentials_schema = [
        Str("token", verbose="Access Token", required=True),
    ]
