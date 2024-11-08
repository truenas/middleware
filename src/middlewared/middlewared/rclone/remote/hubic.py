from middlewared.rclone.base import BaseRcloneRemote


class HubicRcloneRemote(BaseRcloneRemote):
    name = "HUBIC"
    title = "Hubic"

    buckets = True
    bucket_title = "Container"

    fast_list = True

    rclone_type = "hubic"
