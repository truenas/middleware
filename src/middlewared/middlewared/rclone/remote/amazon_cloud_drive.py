from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class AmazonCloudDriveRcloneRemote(BaseRcloneRemote):
    name = "AMAZON_CLOUD_DRIVE"
    title = "Amazon Cloud Drive"

    rclone_type = "amazon cloud drive"

    credentials_schema = [
        Str("client_id", title="Amazon Application Client ID", required=True),
        Str("client_secret", title="Application Key", required=True),
    ]
