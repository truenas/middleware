from middlewared.rclone.base import BaseRcloneRemote


class AzureBlobRcloneRemote(BaseRcloneRemote):
    name = "AZUREBLOB"
    title = "Microsoft Azure Blob Storage"

    buckets = True
    bucket_title = "Container"

    fast_list = True

    rclone_type = "azureblob"

    def get_task_extra(self, task):
        return {"chunk_size": "100Mi"}
