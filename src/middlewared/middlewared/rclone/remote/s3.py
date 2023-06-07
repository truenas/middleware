import textwrap

import boto3
from botocore.client import Config

from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Bool, Int, Str
from middlewared.utils.lang import undefined


class S3RcloneRemote(BaseRcloneRemote):
    name = "S3"
    title = "Amazon S3"

    buckets = True

    fast_list = True

    rclone_type = "s3"

    credentials_schema = [
        Str("access_key_id", title="Access Key ID", required=True),
        Str("secret_access_key", title="Secret Access Key", required=True),
        Str("endpoint", title="Endpoint URL", default=""),
        Str("region", title="Region", default=""),
        Bool("skip_region", title="Endpoint does not support regions", default=False),
        Bool("signatures_v2", title="Use v2 signatures", default=False),
        Int("max_upload_parts", title="Maximum number of parts in a multipart upload", description=textwrap.dedent("""\
            This option defines the maximum number of multipart chunks to use when doing a multipart upload.
            This can be useful if a service does not support the AWS S3 specification of 10,000 chunks (e.g. Scaleway).
        """), default=10000),
    ]

    task_schema = [
        Str("region", title="Region", default=""),
        Str("encryption", title="Server-Side Encryption", enum=[None, "AES256"], default=None, null=True),
        Str("storage_class", title="The storage class to use", enum=["", "STANDARD", "REDUCED_REDUNDANCY",
                                                                     "STANDARD_IA", "ONEZONE_IA", "INTELLIGENT_TIERING",
                                                                     "GLACIER", "DEEP_ARCHIVE"]),
    ]

    def _get_client(self, credentials):
        config = None

        if credentials["attributes"].get("signatures_v2", False):
            config = Config(signature_version="s3")

        client = boto3.client(
            "s3",
            config=config,
            endpoint_url=credentials["attributes"].get("endpoint", "").strip() or None,
            region_name=credentials["attributes"].get("region", "").strip() or None,
            aws_access_key_id=credentials["attributes"]["access_key_id"],
            aws_secret_access_key=credentials["attributes"]["secret_access_key"],
        )
        return client

    async def pre_save_task(self, task, credentials, verrors):
        if task["attributes"]["encryption"] not in (None, "", "AES256"):
            verrors.add("encryption", 'Encryption should be null or "AES256"')

        if not credentials["attributes"].get("skip_region", False):
            if not credentials["attributes"].get("region", "").strip():
                response = await self.middleware.run_in_thread(
                    self._get_client(credentials).get_bucket_location, Bucket=task["attributes"]["bucket"]
                )
                task["attributes"]["region"] = response["LocationConstraint"] or "us-east-1"

    async def get_credentials_extra(self, credentials):
        result = {}

        if (credentials["attributes"].get("endpoint") or "").rstrip("/").endswith(".scw.cloud"):
            if credentials["attributes"].get("max_upload_parts", 10000) == 10000:
                result["max_upload_parts"] = 1000

        return result

    async def get_task_extra(self, task):
        result = dict(
            encryption=undefined,
            server_side_encryption=task["attributes"].get("encryption") or "",
            skip_region=undefined,
            signatures_v2=undefined,
        )

        if not task["credentials"]["attributes"].get("skip_region", False):
            if task["credentials"]["attributes"].get("region", "").strip():
                if not (task["attributes"].get("region") or "").strip():
                    result["region"] = task["credentials"]["attributes"]["region"]
            else:
                # Some legacy tasks have region=None, it's easier to fix it here than in migration
                result["region"] = task["attributes"].get("region") or "us-east-1"
        else:
            if task["credentials"]["attributes"].get("signatures_v2", False):
                result["region"] = "other-v2-signature"
            else:
                result["region"] = ""

        return result

    def get_restic_config(self, task):
        url = task["credentials"]["attributes"].get("endpoint", "").rstrip("/")
        if not url:
            url = "s3.amazonaws.com"

        env = {
            "AWS_ACCESS_KEY_ID": task["credentials"]["attributes"]["access_key_id"],
            "AWS_SECRET_ACCESS_KEY": task["credentials"]["attributes"]["secret_access_key"],
        }

        return url, env
