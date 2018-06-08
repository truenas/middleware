from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class MegaRcloneRemote(BaseRcloneRemote):
    name = "MEGA"
    title = "Mega"

    rclone_type = "mega"

    credentials_schema = [
        Str("user", verbose="Username", required=True),
        Str("pass", verbose="Password", required=True),
    ]
