from middlewared.api.current import PCloudCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote


class PcloudRcloneRemote(BaseRcloneRemote[PCloudCredentialsModel]):
    credentials_schema = PCloudCredentialsModel

    name = "PCLOUD"
    title = "pCloud"

    rclone_type = "pcloud"

    credentials_oauth = True
    credentials_oauth_name = "pcloud2"
    refresh_credentials = ["token"]
