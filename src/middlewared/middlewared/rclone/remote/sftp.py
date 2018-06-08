from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Int, Str


class SFTPRcloneRemote(BaseRcloneRemote):
    name = "SFTP"
    title = "SFTP"

    rclone_type = "sftp"

    credentials_schema = [
        Str("host", verbose="Host", required=True),
        Int("port", verbose="Port"),
        Str("user", verbose="Username", required=True),
        Str("pass", verbose="Password", required=True),
        Str("key_file", verbose="PEM-encoded private key file path", required=True),
    ]
