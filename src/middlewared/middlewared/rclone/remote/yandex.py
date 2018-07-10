from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class WebDavRcloneRemote(BaseRcloneRemote):
    name = "YANDEX"
    title = "Yandex"

    fast_list = True

    rclone_type = "yandex"

    credentials_schema = [
        Str("token", title="Access Token", required=True),
    ]
