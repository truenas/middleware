from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class PcloudRcloneRemote(BaseRcloneRemote):
    name = "PCLOUD"
    title = "pCloud"

    rclone_type = "pcloud"

    credentials_schema = [
        Str("token", verbose="Access Token", required=True),
    ]
