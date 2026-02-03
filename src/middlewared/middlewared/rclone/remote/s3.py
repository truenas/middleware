import boto3
from botocore.client import Config

from middlewared.rclone.base import BaseRcloneRemote
from middlewared.utils.lang import undefined


class S3RcloneRemote(BaseRcloneRemote):
    name = "S3"
    title = "Amazon S3"

    buckets = True

    fast_list = True

    rclone_type = "s3"

    task_attributes = ["region", "encryption", "storage_class"]

    def _get_client(self, credentials):
        config = None

        if credentials["provider"].get("signatures_v2", False):
            config = Config(signature_version="s3")

        client = boto3.client(
            "s3",
            config=config,
            endpoint_url=credentials["provider"].get("endpoint", "").strip() or None,
            region_name=credentials["provider"].get("region", "").strip() or None,
            aws_access_key_id=credentials["provider"]["access_key_id"],
            aws_secret_access_key=credentials["provider"]["secret_access_key"],
        )
        return client

    def validate_task_basic(self, task, credentials, verrors):
        if task["attributes"]["encryption"] not in (None, "", "AES256"):
            verrors.add("encryption", 'Encryption should be null or "AES256"')

        if not credentials["provider"].get("skip_region", False):
            if not credentials["provider"].get("region", "").strip():
                response = self._get_client(credentials).get_bucket_location(Bucket=task["attributes"]["bucket"])
                task["attributes"]["region"] = response["LocationConstraint"] or "us-east-1"

    def get_credentials_extra(self, credentials):
        result = {"provider": credentials["provider"].get("provider", "Other")}

        if (credentials["provider"].get("endpoint") or "").rstrip("/").endswith(".scw.cloud"):
            if credentials["provider"].get("max_upload_parts", 10000) == 10000:
                result["max_upload_parts"] = 1000

        return result

    def get_task_extra(self, task):
        result = dict(
            encryption=undefined,
            server_side_encryption=task["attributes"].get("encryption") or "",
            skip_region=undefined,
            signatures_v2=undefined,
        )

        if not task["credentials"]["provider"].get("skip_region", False):
            if task["credentials"]["provider"].get("region", "").strip():
                if not (task["attributes"].get("region") or "").strip():
                    result["region"] = task["credentials"]["provider"]["region"]
            else:
                # Some legacy tasks have region=None, it's easier to fix it here than in migration
                result["region"] = task["attributes"].get("region") or "us-east-1"
        else:
            if task["credentials"]["provider"].get("signatures_v2", False):
                result["region"] = "other-v2-signature"
            else:
                result["region"] = ""

        return result

    def get_restic_config(self, task):
        url = task["credentials"]["provider"].get("endpoint", "").rstrip("/")
        if not url:
            if region := task["attributes"].get("region") or task["credentials"]["provider"].get("region"):
                url = f"s3.{region}.amazonaws.com"
            else:
                url = "s3.amazonaws.com"

        env = {
            "AWS_ACCESS_KEY_ID": task["credentials"]["provider"]["access_key_id"],
            "AWS_SECRET_ACCESS_KEY": task["credentials"]["provider"]["secret_access_key"],
        }

        return url, env
