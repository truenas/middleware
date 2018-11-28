from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class AzureBlobRcloneRemote(BaseRcloneRemote):
    name = "AZUREBLOB"
    title = "Microsoft Azure Blob Storage"

    buckets = True
    bucket_title = "Container"

    fast_list = True

    rclone_type = "azureblob"

    credentials_schema = [
        Str("account", title="Account Name", required=True),
        Str("key", title="Account Key", required=True),
    ]
