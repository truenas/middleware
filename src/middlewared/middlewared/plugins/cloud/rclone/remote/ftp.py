from middlewared.api.current import FTPCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote


class FTPRcloneRemote(BaseRcloneRemote[FTPCredentialsModel]):
    credentials_schema = FTPCredentialsModel

    name = "FTP"
    title = "FTP"

    rclone_type = "ftp"
