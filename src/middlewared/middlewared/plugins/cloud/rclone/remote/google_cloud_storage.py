from __future__ import annotations

import json
from typing import Any

from middlewared.api.current import GoogleCloudStorageCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote


class GoogleCloudStorageRcloneRemote(BaseRcloneRemote[GoogleCloudStorageCredentialsModel]):
    credentials_schema = GoogleCloudStorageCredentialsModel

    name = "GOOGLE_CLOUD_STORAGE"
    title = "Google Cloud Storage"

    buckets = True

    fast_list = True

    rclone_type = "google cloud storage"

    task_attributes = ["bucket_policy_only"]

    def get_credentials_extra(self, credentials: GoogleCloudStorageCredentialsModel) -> dict[str, Any]:
        service_account_credentials = credentials.service_account_credentials.get_secret_value()
        return dict(
            service_account_credentials=service_account_credentials.replace("\r", "").replace("\n", ""),
            project_number=json.loads(service_account_credentials)["project_id"],
        )
