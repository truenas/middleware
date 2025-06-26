import json

from middlewared.rclone.base import BaseRcloneRemote


class GoogleCloudStorageRcloneRemote(BaseRcloneRemote):
    name = "GOOGLE_CLOUD_STORAGE"
    title = "Google Cloud Storage"

    buckets = True

    fast_list = True

    rclone_type = "google cloud storage"

    task_attributes = ["bucket_policy_only"]

    async def get_credentials_extra(self, credentials):
        return dict(
            service_account_credentials=(credentials["provider"]["service_account_credentials"].
                                         replace("\r", "").
                                         replace("\n", "")),
            project_number=json.loads(credentials["provider"]["service_account_credentials"])["project_id"],
        )
