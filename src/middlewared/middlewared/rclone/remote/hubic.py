from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class HubicRcloneRemote(BaseRcloneRemote):
    name = "HUBIC"
    title = "Hubic"

    buckets = True

    rclone_type = "hubic"

    credentials_schema = [
        Str("token", verbose="Access Token", required=True),
    ]
