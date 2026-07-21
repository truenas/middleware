from __future__ import annotations

from typing import TYPE_CHECKING, Any

import boto3
from botocore.client import Config

from middlewared.api.current import S3CredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote
from middlewared.utils.lang import undefined

if TYPE_CHECKING:
    from middlewared.api.current import CloudTaskAttributes
    from middlewared.service_exception import ValidationErrors


class S3RcloneRemote(BaseRcloneRemote[S3CredentialsModel]):
    credentials_schema = S3CredentialsModel

    name = "S3"
    title = "Amazon S3"

    buckets = True

    fast_list = True

    rclone_type = "s3"

    task_attributes = ["region", "encryption", "storage_class"]

    def _get_client(self, credentials: S3CredentialsModel) -> Any:
        config = None

        if credentials.signatures_v2.get_secret_value():
            config = Config(signature_version="s3")

        client = boto3.client(
            "s3",
            config=config,
            endpoint_url=credentials.endpoint.strip() or None,
            region_name=credentials.region.get_secret_value().strip() or None,
            aws_access_key_id=credentials.access_key_id.get_secret_value(),
            aws_secret_access_key=credentials.secret_access_key.get_secret_value(),
        )
        return client

    def validate_task_basic(
        self,
        attributes: CloudTaskAttributes,
        credentials: S3CredentialsModel,
        verrors: ValidationErrors,
    ) -> None:
        if attributes.encryption not in (None, "", "AES256"):
            verrors.add("encryption", 'Encryption should be null or "AES256"')

        if not credentials.skip_region.get_secret_value():
            if not credentials.region.get_secret_value().strip():
                response = self._get_client(credentials).get_bucket_location(Bucket=attributes.bucket)
                attributes.region = response["LocationConstraint"] or "us-east-1"

    def get_credentials_extra(self, credentials: S3CredentialsModel) -> dict[str, Any]:
        result: dict[str, Any] = {"provider": credentials.provider or "Other"}

        if credentials.endpoint.rstrip("/").endswith(".scw.cloud"):
            if credentials.max_upload_parts.get_secret_value() == 10000:
                result["max_upload_parts"] = 1000

        return result

    def get_task_extra(self, attributes: CloudTaskAttributes, credentials: S3CredentialsModel) -> dict[str, Any]:
        result: dict[str, Any] = dict(
            encryption=undefined,
            server_side_encryption=attributes.encryption or "",
            skip_region=undefined,
            signatures_v2=undefined,
        )

        if not credentials.skip_region.get_secret_value():
            if credentials.region.get_secret_value().strip():
                if not (attributes.region or "").strip():
                    result["region"] = credentials.region.get_secret_value()
            else:
                # Some legacy tasks have region=None, it's easier to fix it here than in migration
                result["region"] = attributes.region or "us-east-1"
        else:
            if credentials.signatures_v2.get_secret_value():
                result["region"] = "other-v2-signature"
            else:
                result["region"] = ""

        return result

    def get_restic_config(
        self,
        attributes: CloudTaskAttributes,
        credentials: S3CredentialsModel,
    ) -> tuple[str, dict[str, str]]:
        url = credentials.endpoint.rstrip("/")
        if not url:
            if region := attributes.region or credentials.region.get_secret_value():
                url = f"s3.{region}.amazonaws.com"
            else:
                url = "s3.amazonaws.com"

        env = {
            "AWS_ACCESS_KEY_ID": credentials.access_key_id.get_secret_value(),
            "AWS_SECRET_ACCESS_KEY": credentials.secret_access_key.get_secret_value(),
        }

        return url, env
