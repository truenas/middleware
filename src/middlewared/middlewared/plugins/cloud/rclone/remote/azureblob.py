from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api.current import AzureBlobCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote

if TYPE_CHECKING:
    from middlewared.api.current import CloudTaskAttributes


class AzureBlobRcloneRemote(BaseRcloneRemote[AzureBlobCredentialsModel]):
    credentials_schema = AzureBlobCredentialsModel

    name = "AZUREBLOB"
    title = "Microsoft Azure Blob Storage"

    buckets = True
    bucket_title = "Container"

    fast_list = True

    rclone_type = "azureblob"

    def get_task_extra(self, attributes: CloudTaskAttributes, credentials: AzureBlobCredentialsModel) -> dict[str, Any]:
        return {"chunk_size": "100Mi"}
