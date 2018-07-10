from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class B2RcloneRemote(BaseRcloneRemote):
    name = "B2"
    title = "Backblaze B2"

    buckets = True

    fast_list = True

    rclone_type = "b2"

    credentials_schema = [
        Str("account", title="Account ID", required=True),
        Str("key", title="Application Key", required=True),
    ]
