from middlewared.rclone.base import BaseRcloneRemote


class MegaRcloneRemote(BaseRcloneRemote):
    name = "MEGA"
    title = "Mega"

    rclone_type = "mega"
