from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Int, Str


class SFTPRcloneRemote(BaseRcloneRemote):
    name = "SFTP"
    title = "SFTP"

    rclone_type = "sftp"

    credentials_schema = [
        Str("host", title="Host", required=True),
        Int("port", title="Port"),
        Str("user", title="Username", required=True),
        Str("pass", title="Password", required=True),
        Str("key_file", title="PEM-encoded private key file path", required=True),
    ]
