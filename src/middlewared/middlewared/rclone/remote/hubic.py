from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class HubicRcloneRemote(BaseRcloneRemote):
    name = "HUBIC"
    title = "Hubic"

    buckets = True
    bucket_title = "Container"

    fast_list = True

    rclone_type = "hubic"

    credentials_schema = [
        Str("token", title="Access Token", required=True, max_length=None),
    ]
