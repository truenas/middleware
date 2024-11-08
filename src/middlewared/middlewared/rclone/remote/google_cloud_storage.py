import json
import textwrap

from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Bool


class GoogleCloudStorageRcloneRemote(BaseRcloneRemote):
    name = "GOOGLE_CLOUD_STORAGE"
    title = "Google Cloud Storage"

    buckets = True

    fast_list = True

    rclone_type = "google cloud storage"

    task_schema = [
        Bool("bucket_policy_only", title="Bucket Policy Only", description=textwrap.dedent("""\
            Access checks should use bucket-level IAM policies.
            If you want to upload objects to a bucket with Bucket Policy Only set then you will need to set this.
        """), default=False),
    ]

    async def get_credentials_extra(self, credentials):
        return dict(
            service_account_credentials=(credentials["provider"]["service_account_credentials"].
                                         replace("\r", "").
                                         replace("\n", "")),
            project_number=json.loads(credentials["provider"]["service_account_credentials"])["project_id"],
        )
