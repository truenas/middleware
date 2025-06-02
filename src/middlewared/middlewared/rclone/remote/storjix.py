import errno
import io
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from aws_requests_auth.aws_auth import AWSRequestsAuth
import boto3
import botocore
import requests

from middlewared.rclone.base import BaseRcloneRemote
from middlewared.service_exception import CallError
from middlewared.utils.network import INTERNET_TIMEOUT


class StorjIxError(CallError):
    pass


class StorjIxRcloneRemote(BaseRcloneRemote):
    name = "STORJ_IX"
    title = "Storj"

    buckets = True
    can_create_bucket = True
    custom_list_buckets = True

    fast_list = True

    rclone_type = "s3"

    async def create_bucket(self, credentials, name):
        def create_bucket_sync():
            provider = credentials["provider"]
            s3_client = boto3.client(
                "s3",
                config=botocore.config.Config(user_agent="ix-storj-1"),
                endpoint_url=provider["endpoint"],
                aws_access_key_id=provider["access_key_id"],
                aws_secret_access_key=provider["secret_access_key"],
            )
            # s3 bucket naming rules: https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html
            try:
                s3_client.create_bucket(Bucket=name)
            except s3_client.exceptions.BucketAlreadyExists as e:
                raise CallError(str(e), errno=errno.EEXIST)
            except botocore.exceptions.ParamValidationError as e:
                raise StorjIxError("The bucket name can only contain lowercase letters, numbers, and hyphens.",
                                   errno.EINVAL, str(e))
            except botocore.exceptions.ClientError as e:
                if "InvalidBucketName" in e.args[0]:
                    raise StorjIxError("The bucket name must be between 3-63 characters in length and cannot contain "
                                       "uppercase.", errno.EINVAL, str(e))
                raise

        return await self.middleware.run_in_thread(create_bucket_sync)

    async def list_buckets(self, credentials):
        def list_buckets_sync():
            provider = credentials["provider"]
            endpoint = provider["endpoint"]

            auth = AWSRequestsAuth(aws_access_key=provider["access_key_id"],
                                   aws_secret_access_key=provider["secret_access_key"],
                                   aws_host=urlparse(endpoint).hostname,
                                   aws_region="",
                                   aws_service="s3")

            r = requests.get(f"{endpoint}?attribution", auth=auth, timeout=INTERNET_TIMEOUT)
            r.raise_for_status()

            ns = "{http://s3.amazonaws.com/doc/2006-03-01/}"
            return [
                {
                    "name": bucket.find(f"{ns}Name").text,
                    "time": bucket.find(f"{ns}CreationDate").text,
                    "enabled": "ix-storj-1" in (bucket.find(f"{ns}Attribution").text or ""),
                }
                for bucket in ET.parse(io.StringIO(r.text)).iter(f"{ns}Bucket")
            ]

        return await self.middleware.run_in_thread(list_buckets_sync)

    async def get_credentials_extra(self, credentials):
        return {"endpoint": credentials["provider"]["endpoint"], "provider": "Other"}

    async def get_task_extra(self, task):
        # Storj recommended these settings
        return {
            "chunk_size": "64M",
            "disable_http2": "true",
            "upload_cutoff": "64M",
        }

    def get_restic_config(self, task):
        provider = task["credentials"]["provider"]
        env = {
            "AWS_ACCESS_KEY_ID": provider["access_key_id"],
            "AWS_SECRET_ACCESS_KEY": provider["secret_access_key"],
        }
        return urlparse(provider["endpoint"]).hostname, env
