from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Int, Str


class FTPRcloneRemote(BaseRcloneRemote):
    name = "FTP"
    title = "FTP"

    rclone_type = "ftp"

    credentials_schema = [
        Str("host", verbose="Host", required=True),
        Int("port", verbose="Port"),
        Str("user", verbose="Username", required=True),
        Str("pass", verbose="Password", required=True),
    ]
