from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Int, Str


class FTPRcloneRemote(BaseRcloneRemote):
    name = "FTP"
    title = "FTP"

    rclone_type = "ftp"

    credentials_schema = [
        Str("host", title="Host", required=True),
        Int("port", title="Port"),
        Str("user", title="Username", required=True),
        Str("pass", title="Password", required=True),
    ]
