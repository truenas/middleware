from middlewared.api.current import BoxCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote


class BoxRcloneRemote(BaseRcloneRemote[BoxCredentialsModel]):
    credentials_schema = BoxCredentialsModel

    name = "BOX"
    title = "Box"

    rclone_type = "box"

    credentials_oauth = True
    refresh_credentials = ["token"]
