from typing import Any

from middlewared.api.current import CloudTaskAttributes, CredentialsEntry
from middlewared.rclone.base import BaseRcloneRemote


class AzureBlobRcloneRemote(BaseRcloneRemote):
    name = "AZUREBLOB"
    title = "Microsoft Azure Blob Storage"

    buckets = True
    bucket_title = "Container"

    fast_list = True

    rclone_type = "azureblob"

    def get_task_extra(self, attributes: CloudTaskAttributes, credentials: CredentialsEntry) -> dict[str, Any]:
        return {"chunk_size": "100Mi"}
