from middlewared.rclone.base import BaseRcloneRemote


class FTPRcloneRemote(BaseRcloneRemote):
    name = "FTP"
    title = "FTP"

    rclone_type = "ftp"
