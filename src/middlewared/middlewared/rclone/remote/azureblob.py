import re

from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str
from middlewared.validators import Match, URL


class AzureBlobRcloneRemote(BaseRcloneRemote):
    name = "AZUREBLOB"
    title = "Microsoft Azure Blob Storage"

    buckets = True
    bucket_title = "Container"

    fast_list = True

    rclone_type = "azureblob"

    credentials_schema = [
        Str("account", title="Account Name", required=True, validators=[
            Match(r"^[a-z0-9\-.]+$", re.IGNORECASE,
                  "Account Name field can only contain alphanumeric characters, - and .")
        ]),
        Str("key", title="Account Key", required=True),
        Str("endpoint", title="Endpoint", default="", validators=[URL(empty=True)]),
    ]

    async def get_task_extra(self, task):
        return {"chunk_size": "100Mi"}
