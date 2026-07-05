from typing import Any

import boto3
from botocore.client import Config

from middlewared.api.current import CloudTaskAttributes, CredentialsEntry
from middlewared.rclone.base import BaseRcloneRemote
from middlewared.service_exception import ValidationErrors
from middlewared.utils.lang import undefined


class S3RcloneRemote(BaseRcloneRemote):
    name = "S3"
    title = "Amazon S3"

    buckets = True

    fast_list = True

    rclone_type = "s3"

    task_attributes = ["region", "encryption", "storage_class"]

    def _get_client(self, credentials: CredentialsEntry):
        provider = self._provider_config(credentials)

        config = None

        if provider.get("signatures_v2", False):
            config = Config(signature_version="s3")

        client = boto3.client(
            "s3",
            config=config,
            endpoint_url=provider.get("endpoint", "").strip() or None,
            region_name=provider.get("region", "").strip() or None,
            aws_access_key_id=provider["access_key_id"],
            aws_secret_access_key=provider["secret_access_key"],
        )
        return client

    def validate_task_basic(
        self, attributes: CloudTaskAttributes, credentials: CredentialsEntry, verrors: ValidationErrors,
    ) -> None:
        provider = self._provider_config(credentials)

        if attributes.encryption not in (None, "", "AES256"):
            verrors.add("encryption", 'Encryption should be null or "AES256"')

        if not provider.get("skip_region", False):
            if not provider.get("region", "").strip():
                response = self._get_client(credentials).get_bucket_location(Bucket=attributes.bucket)
                attributes.region = response["LocationConstraint"] or "us-east-1"

    def get_credentials_extra(self, credentials: CredentialsEntry) -> dict[str, Any]:
        provider = self._provider_config(credentials)

        result: dict[str, Any] = {"provider": provider.get("provider", "Other")}

        if (provider.get("endpoint") or "").rstrip("/").endswith(".scw.cloud"):
            if provider.get("max_upload_parts", 10000) == 10000:
                result["max_upload_parts"] = 1000

        return result

    def get_task_extra(self, attributes: CloudTaskAttributes, credentials: CredentialsEntry) -> dict[str, Any]:
        provider = self._provider_config(credentials)
        attrs = attributes.model_dump(by_alias=True)

        result: dict[str, Any] = dict(
            encryption=undefined,
            server_side_encryption=attrs.get("encryption") or "",
            skip_region=undefined,
            signatures_v2=undefined,
        )

        if not provider.get("skip_region", False):
            if provider.get("region", "").strip():
                if not (attrs.get("region") or "").strip():
                    result["region"] = provider["region"]
            else:
                # Some legacy tasks have region=None, it's easier to fix it here than in migration
                result["region"] = attrs.get("region") or "us-east-1"
        else:
            if provider.get("signatures_v2", False):
                result["region"] = "other-v2-signature"
            else:
                result["region"] = ""

        return result

    def get_restic_config(
        self, credentials: CredentialsEntry, attributes: CloudTaskAttributes,
    ) -> tuple[str, dict[str, str]]:
        provider = self._provider_config(credentials)
        attrs = attributes.model_dump(by_alias=True)

        url = provider.get("endpoint", "").rstrip("/")
        if not url:
            if region := attrs.get("region") or provider.get("region"):
                url = f"s3.{region}.amazonaws.com"
            else:
                url = "s3.amazonaws.com"

        env = {
            "AWS_ACCESS_KEY_ID": provider["access_key_id"],
            "AWS_SECRET_ACCESS_KEY": provider["secret_access_key"],
        }

        return url, env
