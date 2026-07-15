from middlewared.api.current import HubicCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote


class HubicRcloneRemote(BaseRcloneRemote[HubicCredentialsModel]):
    credentials_schema = HubicCredentialsModel

    name = "HUBIC"
    title = "Hubic"

    buckets = True
    bucket_title = "Container"

    fast_list = True

    rclone_type = "hubic"
